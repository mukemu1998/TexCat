import sys
import tempfile
import unittest
from pathlib import Path

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
                        "sizes": [1024],
                        "custom": "",
                        "profile": "detail",
                        "format": "keep",
                        "preserve": True,
                        "append_size_suffix": True,
                    },
                }
            ],
        }

    def test_append_and_clear_workflow_history(self) -> None:
        first = tb.workflow_history_entry(self.sample_payload("步骤一"), self.base / "out_a", "默认输出文件夹", 3, 6, "cancel")
        second = tb.workflow_history_entry(self.sample_payload("步骤二"), self.base / "out_b", "自定义输出目录", 5, 10, "suffix")
        tb.append_workflow_history(first, limit=5)
        tb.append_workflow_history(second, limit=5)

        items = tb.read_workflow_history()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["labels"], ["步骤二"])
        self.assertEqual(items[0]["output_count"], 10)
        self.assertEqual(items[0]["conflict_action"], "suffix")

        removed = tb.clear_workflow_history()
        self.assertEqual(removed, 2)
        self.assertEqual(tb.read_workflow_history(), [])

    def test_append_workflow_history_respects_limit(self) -> None:
        for index in range(5):
            entry = tb.workflow_history_entry(
                self.sample_payload(f"步骤{index}"),
                self.base / f"out_{index}",
                "默认输出文件夹",
                index + 1,
                index + 2,
                "cancel",
            )
            tb.append_workflow_history(entry, limit=3)

        items = tb.read_workflow_history()
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["labels"], ["步骤4"])
        self.assertEqual(items[-1]["labels"], ["步骤2"])


if __name__ == "__main__":
    unittest.main()
