# -*- coding: utf-8 -*-
import unittest
import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).parent
NODE_ROOT = HERE.parent

spec = importlib.util.spec_from_file_location(
    "nai_emphasis_converter",
    str(NODE_ROOT / "__init__.py"),
    submodule_search_locations=[str(NODE_ROOT)],
)
mod = importlib.util.module_from_spec(spec)
sys.modules["nai_emphasis_converter"] = mod
spec.loader.exec_module(mod)

NODE_CLASS_MAPPINGS = mod.NODE_CLASS_MAPPINGS
NODE_DISPLAY_NAME_MAPPINGS = mod.NODE_DISPLAY_NAME_MAPPINGS
WeiLinPromptAnchor = NODE_CLASS_MAPPINGS["WeiLinComfyUIPromptAllInOneGreat"]


class TestWeiLinPromptAnchor(unittest.TestCase):
    def test_mappings_registered(self):
        self.assertIn("WeiLinComfyUIPromptAllInOneGreat", NODE_CLASS_MAPPINGS)
        self.assertIn("WeiLinComfyUIPromptAllInOneNeg", NODE_CLASS_MAPPINGS)
        self.assertIs(NODE_CLASS_MAPPINGS["WeiLinComfyUIPromptAllInOneGreat"], WeiLinPromptAnchor)
        self.assertIs(NODE_CLASS_MAPPINGS["WeiLinComfyUIPromptAllInOneNeg"], WeiLinPromptAnchor)

        self.assertIn("WeiLinComfyUIPromptAllInOneGreat", NODE_DISPLAY_NAME_MAPPINGS)
        self.assertIn("WeiLinComfyUIPromptAllInOneNeg", NODE_DISPLAY_NAME_MAPPINGS)

    def test_passthrough(self):
        anchor = WeiLinPromptAnchor()
        res = anchor.passthrough("masterpiece, 1girl")
        self.assertEqual(res, ("masterpiece, 1girl",))

    def test_input_types(self):
        inputs = WeiLinPromptAnchor.INPUT_TYPES()
        self.assertIn("required", inputs)
        self.assertIn("text", inputs["required"])
        text_spec = inputs["required"]["text"]
        self.assertEqual(text_spec[0], "STRING")
        self.assertTrue(text_spec[1].get("multiline"))


if __name__ == "__main__":
    unittest.main()
