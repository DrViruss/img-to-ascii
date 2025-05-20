from pathlib import Path

from PIL import Image, ImageSequence
from colorama import Style, init

from settings import IMAGE_PATH, ASCII_PATH, FRAME_SEPARATOR

init()

IMAGES_DIR = Path(IMAGE_PATH)
ASCII_DIR = Path(ASCII_PATH)

ASCII_DIR.mkdir(exist_ok=True)

ASCII_CHARS = "@%#*+=-:. "

def resize_image(image, new_width=80):
    width, height = image.size
    aspect_ratio = height / width
    new_height = int(new_width * aspect_ratio * 0.55)
    return image.resize((new_width, new_height))

def pixel_to_ascii(pixel):
    r, g, b = pixel[:3]
    brightness = sum((r, g, b)) / 3
    char = ASCII_CHARS[int(brightness / 255 * (len(ASCII_CHARS) - 1))]
    return f"\x1b[38;2;{r};{g};{b}m{char}{Style.RESET_ALL}"

def image_to_ascii(image: Image.Image):
    image = resize_image(image)
    image = image.convert('RGB')
    pixels = image.getdata()
    ascii_str = ""
    for i in range(len(pixels)):
        ascii_str += pixel_to_ascii(pixels[i])
        if (i + 1) % image.width == 0:
            ascii_str += "\n"
    return ascii_str

def save_ascii_file(path: Path, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def process_static_image(image_path: Path, out_path: Path):
    img = Image.open(image_path)
    ascii_art = image_to_ascii(img)
    save_ascii_file(out_path, ascii_art)

def process_gif_image(gif_path: Path, out_path: Path):
    img = Image.open(gif_path)
    frames_ascii = []
    for frame in ImageSequence.Iterator(img):
        frame_ascii = image_to_ascii(frame.copy())
        frames_ascii.append(frame_ascii)
    save_ascii_file(out_path, f"\n{FRAME_SEPARATOR}\n".join(frames_ascii))

def is_gif(path: Path):
    return path.suffix.lower() == ".gif"

def process_images():
    for image_file in IMAGES_DIR.iterdir():
        if not image_file.is_file():
            continue

        name = image_file.stem
        ascii_file = ASCII_DIR / f"{name}.ascii"

        if ascii_file.exists():
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
