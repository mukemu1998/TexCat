import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import texture_toolbox as tb


class WorkflowHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.original_assets_dir = tb.ASSETS_DIR
        self.original_output_dir = tb.DEFAULT_OUTPUT_DIR
        self.original_template_dir = tb.WORKFLOW_TEMPLATE_DIR
        self.original_history_path = tb.WORKFLOW_HISTORY_PATH
        tb.ASSETS_DIR = self.base / "assets"
        tb.DEFAULT_OUTPUT_DIR = self.base / "output"
        tb.WORKFLOW_TEMPLATE_DIR = self.base / "workflow_templates"
        tb.WORKFLOW_HISTORY_PATH = self.base / "workflow_history.json"

    def tearDown(self) -> None:
        tb.ASSETS_DIR = self.original_assets_dir
        tb.DEFAULT_OUTPUT_DIR = self.original_output_dir
        tb.WORKFLOW_TEMPLATE_DIR = self.original_template_dir
        tb.WORKFLOW_HISTORY_PATH = self.original_history_path
        self.temp_dir.cleanup()

    def sample_payload(self, label: str = "缩放尺寸") -> dict[str, object]:
        return {
            "version": 1,
            "app": "TexCat",
            "mode": "workflow-beta",
            "steps": [
                {
                    "id": "resize-step",
                    "type": "resize",
                    "enabled": True,
                    "label": label,
                    "options": {
                        "sizes": [4],
                        "custom": "",
                        "profile": "detail",
                        "format": "keep",
                        "preserve": True,
                        "append_size_suffix": True,
                    },
                }
            ],
        }

    def make_rgba(self, path: Path, color: tuple[int, int, int, int] = (255, 0, 0, 255), size: tuple[int, int] = (8, 8)) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", size, color).save(path)
        return path

    def history_entry(
        self,
        label: str,
        output_dir: Path,
        *,
        input_mode: str = "folder",
        input_source: str = "",
        output_mode: str = "custom",
        channel_mode: str = "auto",
        conflict_action: str = "cancel",
        input_count: int = 1,
        output_count: int = 1,
    ) -> dict[str, object]:
        return tb.workflow_history_entry(
            self.sample_payload(label),
            output_dir,
            str(output_dir),
            input_count,
            output_count,
            conflict_action,
            input_mode,
            input_source,
            output_mode,
            channel_mode,
        )

    def test_append_and_clear_workflow_history(self) -> None:
        first = self.history_entry("步骤一", self.base / "out_a", input_count=3, output_count=6)
        second = self.history_entry("步骤二", self.base / "out_b", conflict_action="suffix", input_count=5, output_count=10)
        tb.append_workflow_history(first, limit=5)
        tb.append_workflow_history(second, limit=5)

        items = tb.read_workflow_history()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["labels"], ["步骤二"])
        self.assertEqual(items[0]["output_count"], 10)
        self.assertEqual(items[0]["conflict_action"], "suffix")
        self.assertFalse(items[0]["rerunnable"])

        removed = tb.clear_workflow_history()
        self.assertEqual(removed, 2)
        self.assertEqual(tb.read_workflow_history(), [])

    def test_append_workflow_history_respects_limit(self) -> None:
        for index in range(5):
            entry = self.history_entry(f"步骤{index}", self.base / f"out_{index}", input_count=index + 1, output_count=index + 2)
            tb.append_workflow_history(entry, limit=3)

        items = tb.read_workflow_history()
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["labels"], ["步骤4"])
        self.assertEqual(items[-1]["labels"], ["步骤2"])

    def test_rerun_workflow_history_entry_replays_folder_input_with_suffix_conflict(self) -> None:
        input_dir = self.base / "input"
        self.make_rgba(input_dir / "sample.png")
        output_dir = self.base / "output"
        output_dir.mkdir()
        (output_dir / "sample_4x4.png").write_bytes(b"existing")

        entry = self.history_entry(
            "重跑步骤",
            output_dir,
            input_mode="folder",
            input_source=str(input_dir),
            output_mode="custom",
            channel_mode="auto",
            conflict_action="suffix",
            input_count=1,
            output_count=1,
        )
        result = tb.rerun_workflow_history_entry(entry)
        self.assertTrue((output_dir / "sample_4x4_TC.png").exists())
        self.assertEqual(result["history"]["labels"], ["重跑步骤"])
        self.assertTrue(result["history"]["rerunnable"])
        self.assertEqual(len(tb.read_workflow_history()), 1)


if __name__ == "__main__":
    unittest.main()
