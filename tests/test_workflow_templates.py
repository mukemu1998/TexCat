import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import texture_toolbox as tb


class WorkflowTemplateStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.original_assets_dir = tb.ASSETS_DIR
        self.original_output_dir = tb.DEFAULT_OUTPUT_DIR
        self.original_template_dir = tb.WORKFLOW_TEMPLATE_DIR
        tb.ASSETS_DIR = self.base / "assets"
        tb.DEFAULT_OUTPUT_DIR = self.base / "output"
        tb.WORKFLOW_TEMPLATE_DIR = self.base / "workflow_templates"

    def tearDown(self) -> None:
        tb.ASSETS_DIR = self.original_assets_dir
        tb.DEFAULT_OUTPUT_DIR = self.original_output_dir
        tb.WORKFLOW_TEMPLATE_DIR = self.original_template_dir
        self.temp_dir.cleanup()

    def sample_payload(self) -> dict[str, object]:
        return {
            "steps": [
                {
                    "id": "resize-step",
                    "type": "resize",
                    "enabled": True,
                    "label": "缩放尺寸",
                    "summary": "1K，细节优先，KEEP，尺寸后缀",
                    "options": {
                        "sizes": [1024],
                        "custom": "",
                        "profile": "detail",
                        "format": "keep",
                        "preserve": True,
                        "append_size_suffix": True,
                    },
                },
                {
                    "id": "export-step",
                    "type": "export",
                    "enabled": True,
                    "label": "格式与压缩",
                    "summary": "PNG，质量 95",
                    "options": {"format": "png", "quality": 95, "lossless": True},
                },
            ]
        }

    def test_workflow_template_roundtrip_and_listing(self) -> None:
        meta, updated = tb.save_workflow_template("角色贴图流程", self.sample_payload())
        self.assertFalse(updated)
        self.assertEqual(meta["name"], "角色贴图流程")
        self.assertEqual(meta["step_count"], 2)
        self.assertEqual(meta["labels"], ["缩放尺寸", "格式与压缩"])

        items = tb.list_workflow_templates()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["key"], meta["key"])

        loaded = tb.load_workflow_template(str(meta["key"]))
        self.assertEqual(loaded["name"], "角色贴图流程")
        self.assertEqual(len(loaded["steps"]), 2)

        removed = tb.delete_workflow_template(str(meta["key"]))
        self.assertEqual(removed["name"], "角色贴图流程")
        self.assertEqual(tb.list_workflow_templates(), [])

    def test_workflow_template_save_rejects_empty_steps(self) -> None:
        with self.assertRaisesRegex(ValueError, "没有步骤"):
            tb.save_workflow_template("空模板", {"steps": []})


if __name__ == "__main__":
    unittest.main()
