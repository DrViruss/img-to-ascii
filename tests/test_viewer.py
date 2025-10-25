from pathlib import Path
from unittest.mock import patch

from viewer import (
    load_ascii_frames,
    print_frame,
)

class TestViewer:
    @patch("viewer.decompress_ascii")
    @patch("viewer.unpack_content")
    @patch("viewer.apply_diff")
    def test_load_ascii_frames(self, mock_diff, mock_unpack, mock_decompress):
        mock_decompress.return_value = (
            {"compressed": True, "diff": False, "color": True},
            "FRAME1",
        )
        mock_unpack.return_value = ["FRAME1"]
        mock_diff.return_value = ["FRAME1"]

        frames, meta = load_ascii_frames(Path("fake"))
        assert frames == ["FRAME1"]
        assert meta["color"] is True

    @patch("builtins.print")
    @patch("viewer.clear_screen")
    def test_print_frame(self, mock_clear, mock_print):
        print_frame("TEST", "name", 0, 1)
        mock_print.assert_any_call("TEST")