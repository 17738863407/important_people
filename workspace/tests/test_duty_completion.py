from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPLETION_SCRIPT = PROJECT_ROOT / "script3-职务规范3-补全.py"
CLEANING_SCRIPT = PROJECT_ROOT / "script3-职务规范2-清理.py"


def load_script(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载测试脚本：{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DutyCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.completion = load_script(COMPLETION_SCRIPT, "duty_completion_under_test")
        cls.cleaning = cls.completion.load_cleaning_module(CLEANING_SCRIPT)

    def complete(self, duty: str, province: str, city: str, organization: str) -> str:
        row = {
            "职务*": duty,
            "所属省*": province,
            "所属市": city,
            "机构": organization,
        }
        output, _ = self.completion.complete_row_duties(row, self.cleaning)
        return output["职务*"]

    def test_removes_province_before_matching_city_in_completed_duties(self) -> None:
        actual = self.complete(
            "青海省海东市中级人民法院党组成员、青海省海东市中级人民法院副院长",
            "青海省",
            "海东市",
            "海东市中级人民法院",
        )

        self.assertEqual(
            actual,
            "海东市中级人民法院党组成员、海东市中级人民法院副院长",
        )

    def test_removes_province_before_matching_autonomous_prefecture(self) -> None:
        actual = self.complete(
            "青海省海北藏族自治州人民检察院副检察长",
            "青海省",
            "海北藏族自治州",
            "海北藏族自治州人民检察院",
        )

        self.assertEqual(actual, "海北藏族自治州人民检察院副检察长")

    def test_keeps_province_when_city_context_is_missing_or_different(self) -> None:
        cases = (
            ("", "青海省海东市中级人民法院副院长"),
            ("西宁市", "青海省海东市中级人民法院副院长"),
        )
        for city, expected in cases:
            with self.subTest(city=city):
                actual = self.complete(
                    "青海省海东市中级人民法院副院长",
                    "青海省",
                    city,
                    "海东市中级人民法院",
                )
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
