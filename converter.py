import json
import zlib
import argparse

from pathlib import Path
from PIL import Image, ImageSequence
from colorama import Style, init

from settings import IMAGE_PATH, ASCII_PATH, FRAME_SEPARATOR, ASCII_EXTENSION

init()

IMAGES_DIR = Path(IMAGE_PATH)
ASCII_DIR = Path(ASCII_PATH)

ASCII_DIR.mkdir(exist_ok=True)

ASCII_CHARS = "@%#*+=-:. "


def parse_arguments():
    parser = argparse.ArgumentParser(description="Convert images/GIFs to ASCII format.")
    parser.add_argument('--no-compress', action='store_true', help="Disable RLE compression")
    parser.add_argument('--compress-threshold', type=int, default=4, help="Minimum run length for compression")
    parser.add_argument('--no-diff', action='store_true', help="Disable diff mode for GIFs")
    parser.add_argument('--color-mode', type=int, choices=[0, 1, 2], default=2,
                        help="0: grayscale, 1: inverted grayscale, 2: color")
    parser.add_argument('--width', type=int, default=80, help="Custom width for resized images")
    parser.add_argument('--background-color', type=str, default="#000000",
                        help="Background color for transparent areas in hex (e.g., #FFFFFF for white)")
    return parser.parse_args()

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))

def resize_image(image, new_width):
    width, height = image.size
    aspect_ratio = height / width
    new_height = int(new_width * aspect_ratio * 0.55)
    return image.resize((new_width, new_height))

def pixel_to_ascii(pixel, color_mode):
    r, g, b = pixel[:3]
    brightness = sum((r, g, b)) / 3
    char_index = int(brightness / 255 * (len(ASCII_CHARS) - 1))
    if color_mode == 0:
        return ASCII_CHARS[char_index]
    elif color_mode == 1:
        return ASCII_CHARS[::-1][char_index]
    else:
        char = ASCII_CHARS[char_index]
        return f"\x1b[38;2;{r};{g};{b}m{char}{Style.RESET_ALL}"


def compress_line(line, enabled, threshold):
    if not enabled:
        return line
    result = []
    count = 1
    prev = line[0]
    for char in line[1:]:
        if char == prev:
            count += 1
        else:
            if count >= threshold:
                result.append(f"{prev}{count}")
            else:
                result.extend([prev] * count)
            prev = char
            count = 1
    if count >= threshold:
        result.append(f"{prev}{count}")
    else:
        result.extend([prev] * count)
    return ''.join(result)


def image_to_ascii(image: Image.Image, options):
    image = resize_image(image, options.width)
    image = image.convert('RGB')
    pixels = image.getdata()
    lines = []
    for y in range(image.height):
        line = ''.join(pixel_to_ascii(pixels[y * image.width + x], options.color_mode) for x in range(image.width))
        lines.append(compress_line(line, not options.no_compress, options.compress_threshold))
    return lines


def diff_frames(frames):
    diffs = ['\n'.join(frames[0])]
    for i in range(1, len(frames)):
        prev = frames[i - 1]
        curr = frames[i]

        max_len = max(len(prev), len(curr))
        diff = []

        for j in range(max_len):
            pl = prev[j] if j < len(prev) else ''
            cl = curr[j] if j < len(curr) else ''
            diff.append('=' if pl == cl else cl)
        diffs.append('\n'.join(diff))
    return diffs


def save_ascii_file(path: Path, content: str, metadata: dict):
    meta_json = json.dumps(metadata).encode('utf-8')
    content_bytes = content.encode('utf-8')
    combined = meta_json + b"\n" + content_bytes
    compressed = zlib.compress(combined)
    with open(path.with_suffix(f".{ASCII_EXTENSION}"), "wb") as f:
        f.write(compressed)


def process_static_image(image_path: Path, out_path: Path, options):
    img = Image.open(image_path)
    ascii_art = '\n'.join(image_to_ascii(img, options))
    meta = {
        "compressed": not options.no_compress,
        "diff": False,
        "color": options.color_mode == 2
    }
    save_ascii_file(out_path, ascii_art, meta)


def extract_composited_frames(img, background_rgb):
    frames = []
    delays = []
    canvas = Image.new("RGBA", img.size, background_rgb + (0,))
    prev_canvas = None

    for frame_num in range(img.n_frames):
        img.seek(frame_num)
        disposal = img.info.get('disposal', 2)
        duration = img.info.get('duration', 120)
        frame = img.convert("RGBA")
        if img.tile:
            tile = img.tile[0]
            offset = tile[1][:2]
            box = tile[1]
            frame = frame.crop(box)
        else:
            offset = (0, 0)

        if disposal == 2:
            canvas.paste(background_rgb + (255,), (0, 0) + img.size)
        elif disposal == 3 and prev_canvas is not None:
            canvas = prev_canvas.copy()
        canvas.alpha_composite(frame, offset)

        frames.append(canvas.copy().convert("RGBA"))
        delays.append(duration)

        prev_canvas = canvas.copy()

    return frames, delays


def process_gif_image(gif_path: Path, out_path: Path, options):
    img = Image.open(gif_path)
    background_rgb = hex_to_rgb(options.background_color)
    composited_frames, delays = extract_composited_frames(img, background_rgb)
    frames_ascii = []
    for frame in composited_frames:
        frames_ascii.append(image_to_ascii(frame, options))
    max_height = max(len(frame) for frame in frames_ascii)
    compress_enabled = not options.no_compress
    threshold = options.compress_threshold
    empty_line = compress_line(' ' * options.width, compress_enabled, threshold)
    for frame in frames_ascii:
        while len(frame) < max_height:
            frame.append(empty_line)
    if not options.no_diff:
        frames_ascii = diff_frames(frames_ascii)
    else:
        frames_ascii = ['\n'.join(frame) for frame in frames_ascii]
    meta = {
        "compressed": compress_enabled,
        "diff": not options.no_diff,
        "color": options.color_mode == 2,
        "delays": delays
    }
    save_ascii_file(out_path, f"\n{FRAME_SEPARATOR}\n".join(frames_ascii), meta)

def is_gif(path: Path):
    return path.suffix.lower() == ".gif"

def process_images(options):
    for image_file in IMAGES_DIR.iterdir():
        if not image_file.is_file():
            continue
        name = image_file.stem
        ascii_file = ASCII_DIR / f"{name}.{ASCII_EXTENSION}"
        if ascii_file.exists():
            print(f"[!] {ascii_file.name} already converted.")
            continue
        print(f"[→] Converting {image_file.name} into ASCII...")
        try:
            if is_gif(image_file):
                process_gif_image(image_file, ascii_file, options)
            else:
                process_static_image(image_file, ascii_file, options)
            print(f"[✓] {ascii_file.name} successfully converted.")
        except Exception as e:
            print(f"[!] Error on processing {image_file.name}: {e}")

if __name__ == "__main__":
    args = parse_arguments()
    process_images(args)
    print("Done")
