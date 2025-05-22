import json
import zlib

from pathlib import Path
from PIL import Image, ImageSequence
from colorama import Style, init

from settings import IMAGE_PATH, ASCII_PATH, FRAME_SEPARATOR, ASCII_EXTENSION

init()

IMAGES_DIR = Path(IMAGE_PATH)
ASCII_DIR = Path(ASCII_PATH)

ASCII_DIR.mkdir(exist_ok=True)

ASCII_CHARS = "@%#*+=-:. "

ENABLE_COMPRESSION = True
COMPRESSION_THRESHOLD = 4
ENABLE_DIFF = True
ENABLE_COLOR = True


def resize_image(image, new_width=80):
    width, height = image.size
    aspect_ratio = height / width
    new_height = int(new_width * aspect_ratio * 0.55)
    return image.resize((new_width, new_height))

def pixel_to_ascii(pixel):
    r, g, b = pixel[:3]
    brightness = sum((r, g, b)) / 3
    char = ASCII_CHARS[int(brightness / 255 * (len(ASCII_CHARS) - 1))]
    if ENABLE_COLOR:
        return f"\x1b[38;2;{r};{g};{b}m{char}{Style.RESET_ALL}"
    else:
        return char


def compress_line(line):
    result = []
    count = 1
    prev = line[0]
    for char in line[1:]:
        if char == prev:
            count += 1
        else:
            if ENABLE_COMPRESSION and count >= COMPRESSION_THRESHOLD:
                result.append(f"{prev}{count}")
            else:
                result.extend([prev] * count)
            prev = char
            count = 1
    if ENABLE_COMPRESSION and count >= COMPRESSION_THRESHOLD:
        result.append(f"{prev}{count}")
    else:
        result.extend([prev] * count)
    return ''.join(result)


def image_to_ascii(image: Image.Image):
    image = resize_image(image)
    image = image.convert('RGB')
    pixels = image.getdata()
    lines = []
    for y in range(image.height):
        line = ''.join(pixel_to_ascii(pixels[y * image.width + x]) for x in range(image.width))
        lines.append(compress_line(line) if ENABLE_COMPRESSION else line)
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
            if pl == cl:
                diff.append('=')
            else:
                diff.append(cl)

        diffs.append('\n'.join(diff))
    return diffs


def save_ascii_file(path: Path, content: str, metadata: dict):
    meta_json = json.dumps(metadata).encode('utf-8')
    content_bytes = content.encode('utf-8')
    combined = meta_json + b"\n" + content_bytes
    compressed = zlib.compress(combined)
    with open(path.with_suffix(f".{ASCII_EXTENSION}"), "wb") as f:
        f.write(compressed)


def process_static_image(image_path: Path, out_path: Path):
    img = Image.open(image_path)
    ascii_art = '\n'.join(image_to_ascii(img))
    meta = {"compressed": ENABLE_COMPRESSION, "diff": False, "color": ENABLE_COLOR}
    save_ascii_file(out_path, ascii_art, meta)


def process_gif_image(gif_path: Path, out_path: Path):
    img = Image.open(gif_path)
    frames_ascii = [image_to_ascii(frame.copy()) for frame in ImageSequence.Iterator(img)]

    max_height = max(len(frame) for frame in frames_ascii)
    for i, frame in enumerate(frames_ascii):
        while len(frame) < max_height:
            frame.append('')

    if ENABLE_DIFF:
        frames_ascii = diff_frames(frames_ascii)

    meta = {"compressed": ENABLE_COMPRESSION, "diff": ENABLE_DIFF, "color": ENABLE_COLOR}
    save_ascii_file(out_path, f"\n{FRAME_SEPARATOR}\n".join(frames_ascii), meta)

def is_gif(path: Path):
    return path.suffix.lower() == ".gif"

def process_images():
    for image_file in IMAGES_DIR.iterdir():
        if not image_file.is_file():
            continue

        name = image_file.stem
        ascii_file = ASCII_DIR / f"{name}.{ASCII_EXTENSION}"

        if ascii_file.with_suffix(f".{ASCII_EXTENSION}").exists():
            print(f"[!] {ascii_file.name} already converted.")
            continue

        print(f"[→] Converting {image_file.name} into ASCII...")

        try:
            if is_gif(image_file):
                process_gif_image(image_file, ascii_file)
            else:
                process_static_image(image_file, ascii_file)
            print(f"[✓] {ascii_file.name} successfully converted.")
        except Exception as e:
            print(f"[!] Error on processing {image_file.name}: {e}")

if __name__ == "__main__":
    process_images()
    print("Done")
