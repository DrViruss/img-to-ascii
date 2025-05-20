import os
import select
import sys
import termios
import time
import tty

from enum import Enum
from pathlib import Path
from settings import ASCII_PATH, FRAME_SEPARATOR

ASCII_DIR = Path(ASCII_PATH)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

class Mode(Enum):
    AUTO = 1
    STEP = 2

def get_keypress(timeout=None):
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        if timeout is None:
            return sys.stdin.read(1)
        else:
            start = time.time()
            while True:
                if sys.stdin in select.select([sys.stdin], [], [], timeout)[0]:
                    return sys.stdin.read(1)
                if time.time() - start > timeout:
                    return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def load_ascii_frames(ascii_path: Path):
    with open(ascii_path, "r", encoding="utf-8") as f:
        content = f.read()
    frames = content.split(FRAME_SEPARATOR)
    return [frame.strip('\n') for frame in frames]


def print_frame(frame, name, index, total):
    clear_screen()
    print(frame)
    print("\n" + "-"*60)
    print(f"[Name] {name}")
    print(f"[Frame] {index + 1} / {total}")
    print("[a/d] Prv/Nxt\t|\t[Space] Stop/Play\t|\t[x/c] Prv/Nxt frame\t|\t[q] Quit")

def display_ascii_loop(frames, file_name, frame_delay=0.12):
    total_frames = len(frames)
    frame_index = 0
    mode = Mode.AUTO
    draw = True

    while True:
        if draw:
            print_frame(frames[frame_index], file_name, frame_index, total_frames)

        timeout = frame_delay if mode == Mode.AUTO else None
        key = get_keypress(timeout=timeout)
        if key:
            key = key.lower()
            if key == 'q':
                return 'quit'
            elif key == 'd':
                return 'next'
            elif key == 'a':
                return 'prev'
            elif key == ' ':
                mode = Mode.AUTO if mode == Mode.STEP else Mode.STEP
            elif key == 'x':
                draw = True
                mode = Mode.STEP
                frame_index = (frame_index - 1) % total_frames
            elif key == 'c':
                draw = True
                mode = Mode.STEP
                frame_index = (frame_index + 1) % total_frames
        elif mode == Mode.AUTO:
            draw = total_frames > 1
            frame_index = (frame_index + 1) % total_frames


def main():
    ascii_files = sorted(ASCII_DIR.glob("*.ascii"))
    if not ascii_files:
        print(f"Cant find any files in \"{ASCII_PATH}\" folder")
        return

    index = 0
    while True:
        file_path = ascii_files[index]
        frames = load_ascii_frames(file_path)
        action = display_ascii_loop(frames, file_path.stem)

        if action == 'quit':
            clear_screen()
            print("\nBye!\n")
            break
        elif action == 'next':
            index = (index + 1) % len(ascii_files)
        elif action == 'prev':
            index = (index - 1) % len(ascii_files)

if __name__ == "__main__":
    main()