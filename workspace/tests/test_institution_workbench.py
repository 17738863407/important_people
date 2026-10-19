"""验证机构数据工作台的草稿、发布、字段改名和重建修订重放。"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from workspace.institution_catalog.workbench.storage import WorkbenchStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FIELDS = [
    "组织体系",
    "目录链接",
    "机构类型",
    "机构层级",
    "所属省*",
    "所属市",
    "机构名称",
    "机构别称",
    "官网链接",
    "领导链接",
    "脚本序号",
    "备注",
]


class WorkbenchStoreTests(unittest.TestCase):
    """在隔离临时目录中验证工作台核心数据行为。"""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temporary_directory.name)
        self.source_path = self.work_dir / "机构全表.txt"
        shutil.copy2(
            PROJECT_ROOT / "workspace" / "source_data" / "机构主表.txt",
            self.source_path,
        )
        self.expected_record_count = len(self.source_path.read_text(encoding="utf-8-sig").splitlines()) - 1
        self.store = WorkbenchStore(
            self.work_dir / "workbench.db",
            self.source_path,
            self.work_dir / "backup",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_initial_import_and_cell_undo(self) -> None:
        state = self.store.state()
        self.assertEqual(self.expected_record_count, len(state["records"]))
        self.assertEqual(12, len(state["fields"]))
        self.assertEqual(EXPECTED_FIELDS, [field["export_name"] for field in state["fields"]])
        record = state["records"][0]
        old_name = record["data"]["institution_name"]
        result = self.store.update_record(record["record_id"], "institution_name", old_name + "测试")
        self.assertTrue(result["changed"])
        self.assertTrue(self.store.undo()["changed"])
        restored = self.store.state()["records"][0]
        self.assertEqual(old_name, restored["data"]["institution_name"])

    def test_create_duplicate_delete_and_restore(self) -> None:
        first = self.store.state()["records"][0]
        created = self.store.create_record({"institution_name": "测试机构", "script_sequence": ""})
        duplicated = self.store.create_record(duplicate_from=first["record_id"])
        self.assertNotEqual(created["record_id"], duplicated["record_id"])
        self.assertTrue(self.store.set_deleted(created["record_id"], True)["deleted"])
        self.assertFalse(self.store.set_deleted(created["record_id"], False)["deleted"])

    def test_real_field_rename_and_publish(self) -> None:
        self.store.rename_field("institution_name", "机构正式名称")
        result = self.store.publish()
        headers = self.source_path.read_text(encoding="utf-8-sig").splitlines()[0].split("\t")
        self.assertIn("机构正式名称", headers)
        self.assertEqual(self.expected_record_count, result["row_count"])
        self.assertTrue(Path(result["backup_path"]).exists())

    def test_external_rebuild_reapplies_manual_override(self) -> None:
        original_copy = self.work_dir / "original.txt"
        shutil.copy2(self.source_path, original_copy)
        first = self.store.state()["records"][0]
        manual_name = first["data"]["institution_name"] + "（人工修订）"
        self.store.update_record(first["record_id"], "institution_name", manual_name)
        self.store.publish()
        shutil.copy2(original_copy, self.source_path)
        self.assertTrue(self.store.state()["status"]["external_change"])
        result = self.store.reconcile()
        self.assertEqual(self.expected_record_count, result["external_count"])
        names = [record["data"]["institution_name"] for record in self.store.state()["records"]]
        self.assertIn(manual_name, names)

    def test_reconcile_uses_external_header_order_and_removes_obsolete_fields(self) -> None:
        """外部全量表的字段集合与顺序应覆盖网页数据库中的旧结构。"""
        with self.store.transaction() as connection:
            connection.execute(
                "INSERT INTO fields(field_id, source_name, export_name, position) VALUES(?, ?, ?, ?)",
                ("obsolete_field", "旧字段", "旧字段", 4),
            )
            connection.execute("UPDATE fields SET position = 99 WHERE export_name = '官网链接'")

        self.store.reconcile()
        fields = self.store.state()["fields"]
        self.assertEqual(EXPECTED_FIELDS, [field["export_name"] for field in fields])
        self.assertNotIn("旧字段", {field["export_name"] for field in fields})

    def test_web_uses_table_organization_system_order(self) -> None:
        """网页不得另设组织体系固定顺序，应采用正式表记录的出现顺序。"""
        app_source = (
            PROJECT_ROOT
            / "workspace"
            / "institution_catalog"
            / "workbench"
            / "static"
            / "app.js"
        ).read_text(encoding="utf-8")
        self.assertNotIn("ORGANIZATION_SYSTEM_ORDER", app_source)

        table_order = list(
            dict.fromkeys(
                record["data"]["organization_system"]
                for record in self.store.state()["records"]
                if record["data"]["organization_system"]
            )
        )
        self.assertLess(table_order.index("地级四大"), table_order.index("市局领导"))
        self.assertLess(table_order.index("市局领导"), table_order.index("央企"))

    def test_provincial_and_prefecture_four_sets_taxonomy(self) -> None:
        """省地两级四套班子应合并体系，并把原体系及细分属性迁入机构类型。"""
        rows = [record["data"] for record in self.store.state()["records"]]
        old_systems = {
            "省级党委",
            "省级人大",
            "省级政府",
            "省级政协",
            "地级党委",
            "地级人大",
            "地级政府",
            "地级政协",
        }
        self.assertFalse(any(row["organization_system"] in old_systems for row in rows))

        provincial_rows = [row for row in rows if row["organization_system"] == "省级四大"]
        prefecture_rows = [row for row in rows if row["organization_system"] == "地级四大"]
        self.assertEqual(124, len(provincial_rows))
        self.assertEqual(1465, len(prefecture_rows))
        self.assertEqual(
            {"省级党委", "省级人大", "省级政府", "省级政协"},
            {row["institution_type"] for row in provincial_rows},
        )
        self.assertEqual(
            75,
            sum(row["institution_type"].endswith("-副省级城市") for row in prefecture_rows),
        )
        self.assertFalse(
            any(
                row["directory_url"]
                for row in provincial_rows
                if row["institution_type"] == "省级政府"
            )
        )


def main() -> None:
    """运行工作台核心单元测试。"""
    unittest.main()


if __name__ == "__main__":
    main()
