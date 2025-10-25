import json
import zlib
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from colorama import Style

from converter import (
    hex_to_rgb,
    resize_image,
    pixel_to_ascii,
    compress_line,
    image_to_ascii,
    diff_frames,
    process_static_image,
    process_gif_image,
    extract_composited_frames, ASCII_CHARS,
)
from settings import ASCII_EXTENSION, FRAME_SEPARATOR
from viewer import unpack_line, unpack_content, apply_diff, strip_ansi_codes, decompress_ascii

@pytest.fixture
def temp_dirs():
    with tempfile.TemporaryDirectory() as img_dir, tempfile.TemporaryDirectory() as ascii_dir:
        yield Path(img_dir), Path(ascii_dir)

@pytest.fixture
def sample_image():
    img = Image.new("RGB", (100, 50), color=(73, 109, 137))
    return img

@pytest.fixture
def sample_gif():
    frames = [
        Image.new("RGBA", (50, 50), color=(255, 0, 0, 255)),
        Image.new("RGBA", (50, 50), color=(0, 255, 0, 255)),
    ]
    gif_path = tempfile.mktemp(suffix=".gif")
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        disposal=2,
    )
    yield Path(gif_path)
    Path(gif_path).unlink(missing_ok=True)

class TestConverterUtils:
    def test_hex_to_rgb(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)
        assert hex_to_rgb("#000000") == (0, 0, 0)
        assert hex_to_rgb("#FF00FF") == (255, 0, 255)

    def test_resize_image(self, sample_image):
        resized = resize_image(sample_image, 40)
        assert resized.width == 40
        assert resized.height == 11  # 50 * 40 / 100 * 0.55 ≈ 11

    @pytest.mark.parametrize(
        "pixel,color_mode,expected_char",
        [
            ((0, 0, 0), 0, "@"),
            ((255, 255, 255), 0, " "),
            ((0, 0, 0), 1, " "),
            ((255, 255, 255), 1, "@"),
            ((128, 128, 128), 1, "="),
            ((255, 0, 0), 2, "\x1b[38;2;255;0;0m@\x1b[0m"),
        ],
    )

    def test_pixel_to_ascii(self, pixel, color_mode, expected_char):
        result = pixel_to_ascii(pixel, color_mode)
        if color_mode == 2:
            assert result.startswith("\x1b[38;2;")
            char = ASCII_CHARS[int(sum(pixel[:3]) / 3 / 255 * (len(ASCII_CHARS) - 1))]
            assert result.endswith(f"m{char}{Style.RESET_ALL}")
        else:
            assert result == expected_char

    def test_compress_line(self):
        line = "AAAAABBBCC"
        compressed = compress_line(line, enabled=True, threshold=3)
        assert compressed == "A5B3CC"

        short = compress_line("AAB", enabled=True, threshold=3)
        assert short == "AAB"

        disabled = compress_line("AAAAA", enabled=False, threshold=3)
        assert disabled == "AAAAA"

    def test_image_to_ascii(self, sample_image):
        class Opt:
            width = 20
            color_mode = 0
            no_compress = False
            compress_threshold = 3

        lines = image_to_ascii(sample_image, Opt())
        assert len(lines) > 0
        assert all(isinstance(l, str) for l in lines)

    def test_diff_frames(self):
        frame1 = ["ABC", "DEF"]
        frame2 = ["ABX", "DEF"]
        diffed = diff_frames([frame1, frame2])
        assert diffed[0] == "ABC\nDEF"
        assert diffed[1] == "ABX\n="

class TestDecompression:
    def test_unpack_line(self):
        assert unpack_line("A5B3") == "AAAAABBB"
        assert unpack_line("\x1b[31mA\x1b[0m") == "\x1b[31mA\x1b[0m"
        assert unpack_line("A\x1b[31mB5\x1b[0m") == "A\x1b[31mBBBBB\x1b[0m"

    def test_unpack_content(self):
        content = f"A3B2\n{FRAME_SEPARATOR}\nC4"
        frames = unpack_content(content, compressed=True)
        assert frames == ["\nAAABB", "\nCCCC"]

    def test_apply_diff(self):
        frames = ["ABC\nDEF", "==X\n="]
        full = apply_diff(frames)
        assert full == ["ABC\nDEF", "==X\nDEF"]

    def test_strip_ansi_codes(self):
        text = "\x1b[31mRED\x1b[0m"
        assert strip_ansi_codes(text) == "RED"

class TestSaveLoad:
    def test_save_and_load(self, temp_dirs):
        img_dir, ascii_dir = temp_dirs
        img_path = img_dir / "test.png"
        Image.new("RGB", (10, 10)).save(img_path)

        class Opt:
            no_compress = False
            no_diff = True
            color_mode = 0
            width = 20
            background_color = "#000000"
            compress_threshold = 3

        process_static_image(img_path, ascii_dir / "test", Opt())

        ascii_file = ascii_dir / f"test.{ASCII_EXTENSION}"
        assert ascii_file.exists()

        metadata, content = decompress_ascii(ascii_file)
        assert metadata["compressed"] is True
        assert metadata["diff"] is False

class TestStaticImage:
    def test_process_static_image(self, temp_dirs, sample_image):
        img_dir, ascii_dir = temp_dirs
        img_path = img_dir / "sample.png"
        sample_image.save(img_path)

        class Opt:
            no_compress = False
            no_diff = True
            color_mode = 0
            width = 40
            background_color = "#000000"
            compress_threshold = 3

        process_static_image(img_path, ascii_dir / "out", Opt())
        out_file = ascii_dir / f"out.{ASCII_EXTENSION}"
        assert out_file.exists()

class TestGIFFrames:
    def test_extract_composited_frames(self, sample_gif):
        img = Image.open(sample_gif)
        frames, delays = extract_composited_frames(img, (0, 0, 0))
        assert len(frames) == 2
        assert delays == [100, 100]

    @patch("converter.image_to_ascii")
    def test_process_gif_image(self, mock_ascii, temp_dirs, sample_gif):
        img_dir, ascii_dir = temp_dirs
        gif_path = img_dir / "test.gif"
        sample_gif.rename(gif_path)

        mock_ascii.side_effect = lambda img, opt: ["LINE1", "LINE2"]

        class Opt:
            no_compress = False
            no_diff = False
            color_mode = 0
            width = 40
            background_color = "#000000"
            compress_threshold = 3

        process_gif_image(gif_path, ascii_dir / "out", Opt())
        out_file = ascii_dir / f"out.{ASCII_EXTENSION}"
        assert out_file.exists()

        with open(out_file, "rb") as f:
            data = zlib.decompress(f.read())
            meta_end = data.find(b"\n")
            meta = json.loads(data[:meta_end])
            assert meta["diff"] is True
            assert "delays" in meta