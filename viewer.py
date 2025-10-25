import os
import select
import sys
import termios
import time
import tty
import json
import zlib

from enum import Enum
from pathlib import Path
from settings import ASCII_PATH, FRAME_SEPARATOR, ASCII_EXTENSION

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

def decompress_ascii(path: Path):
    with open(path, "rb") as f:
        compressed = f.read()
    decompressed = zlib.decompress(compressed)
    meta_end = decompressed.find(b'\n')
    meta_json = decompressed[:meta_end].decode('utf-8')
    content_bytes = decompressed[meta_end+1:]
    metadata = json.loads(meta_json)
    content = content_bytes.decode('utf-8')
    return metadata, content

import re

def unpack_line(line):
    result = []
    i = 0
    length = len(line)

    while i < length:
        if line[i] == '\x1b':
            end = i + 1
            while end < length and line[end] != 'm':
                end += 1
            end = min(end + 1, length)
            result.append(line[i:end])
            i = end
        else:
            m = re.match(r'([^\d\x1b])(\d+)', line[i:])
            if m:
                char = m.group(1)
                count = int(m.group(2))
                result.append(char * count)
                i += len(m.group(0))
            else:
                result.append(line[i])
                i += 1
    return ''.join(result)

def unpack_content(content, compressed=True):
    frames_raw = content.split(FRAME_SEPARATOR)
    frames = []
    for frame in frames_raw:
        lines = frame.splitlines()
        if compressed:
            lines = [unpack_line(line) for line in lines]
        frames.append(lines)

    max_height = max(len(frame) for frame in frames)
    for frame in frames:
        while len(frame) < max_height:
            frame.insert(0, '')

    return ['\n'.join(frame) for frame in frames]

def apply_diff(frames):
    full_frames = [frames[0].splitlines()]
    for diff_frame in frames[1:]:
        diff_lines = diff_frame.splitlines()
        prev_lines = full_frames[-1]
        new_frame = []
        max_len = max(len(prev_lines), len(diff_lines))
        for j in range(max_len):
            pl = prev_lines[j] if j < len(prev_lines) else ''
            dl = diff_lines[j] if j < len(diff_lines) else ''
            if dl == '=':
                new_frame.append(pl)
            else:
                new_frame.append(dl)
        full_frames.append(new_frame)

    max_height = max(len(frame) for frame in full_frames)
    for frame in full_frames:
        while len(frame) < max_height:
            frame.insert(0, '')

    return ['\n'.join(frame) for frame in full_frames]

def strip_ansi_codes(text):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', text)

def load_ascii_frames(path: Path):
    metadata, content = decompress_ascii(path)
    frames = unpack_content(content, compressed=metadata.get('compressed', True))
    if metadata.get('diff', False):
        frames = apply_diff(frames)
    color_enabled = metadata.get('color', True)
    if not color_enabled:
        frames = [strip_ansi_codes(frame) for frame in frames]
    return frames, metadata

def print_frame(frame, name, index, total):
    clear_screen()
    print(frame)
    print("\n" + "-"*60)
    print(f"[Name] {name}")
    print(f"[Frame] {index + 1} / {total}")
    print("[a/d] Prv/Nxt\t|\t[Space] Stop/Play\t|\t[x/c] Prv/Nxt frame\t|\t[q] Quit")

def display_ascii_loop(frames, file_name, metadata):
    total_frames = len(frames)
    frame_index = 0
    mode = Mode.AUTO
    draw = True
    delays = metadata.get('delays')
    default_delay = 0.12
    while True:
        if draw:
            print_frame(frames[frame_index], file_name, frame_index, total_frames)
        if mode == Mode.AUTO and total_frames > 1:
            delay_ms = delays[frame_index] if delays else default_delay * 1000
            timeout = delay_ms / 1000.0
        else:
            timeout = None
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
    ascii_files = sorted(ASCII_DIR.glob(f"*.{ASCII_EXTENSION}"))
    if not ascii_files:
        print(f"Can't find any supported files in \"{ASCII_DIR}\" folder")
        return

    index = 0
    while True:
        file_path = ascii_files[index]
        try:
            frames, metadata = load_ascii_frames(file_path)
            action = display_ascii_loop(frames, file_path.stem, metadata)
        except Exception as e:
            print(f"[!] Error loading {file_path.name}: {e}")
            action = 'next'
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