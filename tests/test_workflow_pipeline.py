import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import texture_toolbox as tb


class DummyForm:
    def __init__(self, mapping: dict[str, object]) -> None:
        self.mapping = mapping

    def getfirst(self, key: str, default: object = None) -> object:
        value = self.mapping.get(key, default)
        if isinstance(value, list):
            return value[0] if value else default
        return value


class WorkflowPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.output_dir = self.base / "out"
        self.output_dir.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_form(self) -> DummyForm:
        return DummyForm(
            {
                "output_mode": "custom",
                "output": str(self.output_dir),
                "channel_mode": "auto",
                "input_mode": "folder",
                "input": str(self.base),
                "tool": "workflow",
            }
        )

    def make_rgba(self, path: Path, color: tuple[int, int, int, int], size: tuple[int, int] = (8, 8)) -> Path:
        Image.new("RGBA", size, color).save(path)
        return path

    def make_l(self, path: Path, value: int, size: tuple[int, int] = (8, 8)) -> Path:
        Image.new("L", size, value).save(path)
        return path

    def test_merge_sources_payload_uses_upstream_split_results(self) -> None:
        paths = [
            self.make_rgba(self.base / "mask_rgba.png", (255, 64, 0, 128)),
            self.make_l(self.base / "ao.png", 200),
        ]
        payload = {
            "steps": [
                {
                    "id": "split-step",
                    "type": "split",
                    "enabled": True,
                    "options": {
                        "format": "png",
                        "channels": {
                            "l": {"enabled": True, "name": "{name}_L"},
                            "r": {"enabled": True, "name": "{name}_R"},
                            "g": {"enabled": False, "name": "{name}_G"},
                            "b": {"enabled": False, "name": "{name}_B"},
                            "a": {"enabled": True, "name": "{name}_A"},
                        },
                    },
                },
                {
                    "id": "merge-step",
                    "type": "merge",
                    "enabled": True,
                    "options": {
                        "base": "",
                        "output_name": "packed_orm",
                        "format": "png",
                        "specs": tb.workflow_merge_specs_from_value({}),
                    },
                },
            ]
        }
        result = tb.workflow_merge_sources_payload(paths, payload, "merge-step")
        self.assertEqual(result["total"], 3)
        stems = [item["stem"] for item in result["items"]]
        self.assertEqual(stems, ["mask_rgba_R", "mask_rgba_A", "ao_L"])

    def test_workflow_output_items_support_split_merge_resize_export_and_rename(self) -> None:
        paths = [
            self.make_rgba(self.base / "mask_rgba.png", (255, 0, 0, 128)),
            self.make_l(self.base / "ao.png", 180),
        ]
        payload = {
            "steps": [
                {
                    "id": "split-step",
                    "type": "split",
                    "enabled": True,
                    "options": {
                        "format": "png",
                        "channels": {
                            "l": {"enabled": True, "name": "{name}_L"},
                            "r": {"enabled": True, "name": "{name}_R"},
                            "g": {"enabled": False, "name": "{name}_G"},
                            "b": {"enabled": False, "name": "{name}_B"},
                            "a": {"enabled": True, "name": "{name}_A"},
                        },
                    },
                },
                {
                    "id": "merge-step",
                    "type": "merge",
                    "enabled": True,
                    "options": {
                        "base": "",
                        "output_name": "packed_orm",
                        "format": "png",
                        "specs": {
                            "r": {"mode": "file", "file": "2", "channel": "gray"},
                            "g": {"mode": "file", "file": "0", "channel": "gray"},
                            "b": {"mode": "file", "file": "1", "channel": "gray"},
                            "a": {"mode": "default255", "file": "", "channel": "gray"},
                        },
                    },
                },
                {
                    "id": "resize-step",
                    "type": "resize",
                    "enabled": True,
                    "options": {
                        "sizes": [4],
                        "custom": "",
                        "profile": "detail",
                        "format": "keep",
                        "preserve": True,
                        "append_size_suffix": True,
                    },
                },
                {
                    "id": "rename-step",
                    "type": "rename",
                    "enabled": True,
                    "options": {
                        "format": "keep",
                        "steps": [
                            {"op": "prefix", "prefix": "TX_"},
                            {"op": "suffix", "suffix": "_LOD0"},
                        ],
                    },
                },
                {
                    "id": "export-step",
                    "type": "export",
                    "enabled": True,
                    "options": {"format": "png", "quality": 95, "lossless": True},
                },
            ]
        }
        items, warnings = tb.workflow_output_items(paths, self.output_dir, self.make_form(), payload, strict_supported=True)
        self.assertFalse(warnings)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["target"], "TX_packed_orm_4x4_LOD0.png")
        report = tb.save_workflow_item(item, item["source_path"], item["destination"], "auto")
        self.assertTrue(report.path.exists())
        with Image.open(report.path) as saved:
            self.assertEqual(saved.size, (4, 4))

    def test_workflow_preview_marks_existing_output_conflict(self) -> None:
        path = self.make_rgba(self.base / "base_rgba.png", (255, 255, 255, 255))
        existing = self.output_dir / "base_rgba.png"
        existing.write_bytes(b"existing")
        payload = {
            "steps": [
                {
                    "id": "export-step",
                    "type": "export",
                    "enabled": True,
                    "options": {"format": "png", "quality": 95, "lossless": True},
                }
            ]
        }
        items, warnings = tb.workflow_output_items([path], self.output_dir, self.make_form(), payload, strict_supported=True)
        self.assertFalse(warnings)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["conflict"])
        self.assertIn("目标位置已存在", items[0]["reason"])

    def test_workflow_batch_crop_requires_same_size(self) -> None:
        paths = [
            self.make_rgba(self.base / "a.png", (255, 0, 0, 255), (8, 8)),
            self.make_rgba(self.base / "b.png", (0, 255, 0, 255), (16, 8)),
        ]
        payload = {
            "steps": [
                {
                    "id": "crop-step",
                    "type": "crop",
                    "enabled": True,
                    "options": {
                        "mode": "batch",
                        "source_index": 0,
                        "format": "keep",
                        "crops": [{"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5, "name": "{name}_crop1"}],
                    },
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "图片当前尺寸一致"):
            tb.workflow_output_items(paths, self.output_dir, self.make_form(), payload, strict_supported=True)


if __name__ == "__main__":
    unittest.main()
