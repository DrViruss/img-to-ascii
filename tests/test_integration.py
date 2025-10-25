import subprocess
import sys
from pathlib import Path

from PIL import Image

def test_cli_converter(tmp_path, monkeypatch):
    img_dir = tmp_path / "img"
    ascii_dir = tmp_path / "ascii"
    img_dir.mkdir()
    ascii_dir.mkdir()

    img = Image.new("RGB", (20, 20), color="red")
    img.save(img_dir / "test.png")

    converter_path = Path(__file__).parent.parent / "converter.py"

    monkeypatch.setattr("settings.IMAGE_PATH", str(img_dir))
    monkeypatch.setattr("settings.ASCII_PATH", str(ascii_dir))

    result = subprocess.run(
        [sys.executable, str(converter_path), "--width", "20"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    print(result.stdout)
    print(result.stderr, file=sys.stderr)

    assert result.returncode == 0
    assert (ascii_dir / "test.ascii").exists()

