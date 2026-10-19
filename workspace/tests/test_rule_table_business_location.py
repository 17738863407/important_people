from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from crawler_core.business_sources import apply_business_source
from crawler_core.exporter import record_to_output_row
from crawler_core.models import PersonRecord
from crawler_core.rule_table import (
    RULE_TABLE_REQUIRED_FIELDS,
    load_generation_records,
    load_rule_table,
)
from crawler_core.runner import apply_business_location
from workspace.tools.同步机构分类到规则主表 import (
    FullRecord,
    MatchResult,
    explicit_other_classification,
    render_rule_table,
    sort_rules_by_full_table,
)


def write_rule_table(path: Path) -> None:
    """写入包含地区、机构分类和别称字段的规则主表。"""
    path.write_text(
        "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
        "市局领导\t\t石家庄市人民政府-政府工作部门\t\t河北省\t石家庄市\t石家庄教育局\t石家庄市教育局、石家庄市教委\t\thttps://example.com/\t0001\t空缺占位\n",
        encoding="utf-8",
    )


class RuleTableBusinessLocationTests(unittest.TestCase):
    """验证规则主表十二列契约、别称校验和业务源注入链路。"""

    def test_rule_table_accepts_aliases_separated_by_ideographic_comma(self) -> None:
        """规则主表应读取用中文顿号分隔的机构别称。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            write_rule_table(source_path)

            records = load_rule_table(source_path)

        self.assertEqual(RULE_TABLE_REQUIRED_FIELDS, ("脚本序号", "机构名称"))
        self.assertEqual(records[0]["所属省*"], "河北省")
        self.assertEqual(records[0]["所属市"], "石家庄市")
        self.assertEqual(records[0]["组织体系"], "市局领导")
        self.assertEqual(records[0]["机构类型"], "石家庄市人民政府-政府工作部门")
        self.assertEqual(records[0]["机构层级"], "")
        self.assertEqual(records[0]["机构别称"], "石家庄市教育局、石家庄市教委")
        self.assertNotIn("启用状态", records[0])

    def test_rule_table_rejects_reordered_or_missing_fields(self) -> None:
        """正式规则主表必须严格遵守用户指定的十二列顺序。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t领导链接\t机构名称\t脚本序号\n"
                "市局领导\thttps://example.com/\t石家庄教育局\t0001\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "表头不符合十二列顺序契约"):
                load_rule_table(source_path)

    def test_business_location_is_injected_into_output(self) -> None:
        """规则主表省市应经业务源注入并进入十二列输出。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            write_rule_table(source_path)

            rule = apply_business_source({"rule_id": "0001"}, source_path)
        row = PersonRecord(
            organization=rule["organization"],
            url=rule["url"],
            name="张三",
            duty="",
            province="旧省份",
            city="旧城市",
            order="7",
        )
        apply_business_location(rule, [row])
        output_row = record_to_output_row(row)

        self.assertEqual(rule["province"], "河北省")
        self.assertEqual(rule["city"], "石家庄市")
        self.assertEqual(rule["organization_aliases"], ("石家庄市教育局", "石家庄市教委"))
        self.assertEqual(output_row["所属省*"], "河北省")
        self.assertEqual(output_row["所属市"], "石家庄市")
        self.assertEqual(output_row["排序*"], "7")
        self.assertNotIn("次序", output_row)

    def test_generation_records_no_longer_require_enabled_status(self) -> None:
        """脚本生成记录应读取全部业务记录并传递扩展字段。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            write_rule_table(source_path)

            records = load_generation_records(source_path)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["所属省*"], "河北省")
        self.assertEqual(records[0]["所属市"], "石家庄市")
        self.assertEqual(records[0]["组织体系"], "市局领导")
        self.assertEqual(records[0]["机构类型"], "石家庄市人民政府-政府工作部门")
        self.assertEqual(records[0]["机构别称"], "石家庄市教育局、石家庄市教委")
        self.assertNotIn("启用状态", records[0])

    def test_classification_writer_preserves_alias(self) -> None:
        """分类同步重新写出主表时必须原样保留别称。"""
        source_row = {
            "组织体系": "市局领导",
            "机构类型": "石家庄市人民政府-政府工作部门",
            "机构层级": "",
            "所属省*": "河北省",
            "所属市": "石家庄市",
            "机构名称": "石家庄教育局",
            "机构别称": "石家庄市教育局、石家庄市教委",
            "领导链接": "https://example.com/",
            "脚本序号": "0001",
            "备注": "",
        }
        matches = {
            "0001": MatchResult(
                "市局领导",
                "石家庄市人民政府-政府工作部门",
                "石家庄教育局",
                "测试",
                "自动通过",
                "高",
                "",
            )
        }

        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            write_rule_table(source_path)
            rendered = render_rule_table(source_path, [source_row], matches).decode("utf-8-sig")
        lines = rendered.splitlines()

        self.assertEqual(
            lines[0],
            "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注",
        )
        self.assertIn("\t石家庄市教育局、石家庄市教委\t", lines[1])

    def test_unknown_organization_system_is_rejected(self) -> None:
        """组织体系只能使用机构全量表当前定义的体系值或留空。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "行政机关\t\t\t\t河北省\t石家庄市\t石家庄教育局\t\t\thttps://example.com/\t0001\t\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "组织体系不在允许范围"):
                load_rule_table(source_path)

    def test_rule_table_accepts_blank_leader_url(self) -> None:
        """机构尚无领导入口时，规则主表应允许领导链接留空。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "法院\t\t青海省-地级法院\t\t青海省\t西宁市\t西宁铁路运输法院\t\t\t\t0001\t\n",
                encoding="utf-8",
            )

            records = load_rule_table(source_path)

        self.assertEqual(records[0]["领导链接"], "")

    def test_court_and_procuratorate_organization_systems_are_accepted(self) -> None:
        """法院、检察院应作为规则主表的正式组织体系值。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "法院\t\t青海省-地级法院\t\t青海省\t西宁市\t西宁市中级人民法院\t\t\thttps://court.example/\t0001\t\n"
                "检察院\t\t青海省-地级检察院\t\t青海省\t西宁市\t西宁市人民检察院\t\t\thttps://procuratorate.example/\t0002\t\n",
                encoding="utf-8",
            )

            records = load_rule_table(source_path)

        self.assertEqual(
            [record["组织体系"] for record in records],
            ["法院", "检察院"],
        )

    def test_other_organization_system_is_accepted(self) -> None:
        """暂时无法归入现有体系的机构允许明确标记为其他。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "其他\t\t\t\t全国\t\t待分类机构\t\t\thttps://example.com/\t0001\t\n",
                encoding="utf-8",
            )

            records = load_rule_table(source_path)

        self.assertEqual(records[0]["组织体系"], "其他")

    def test_other_organization_system_is_preserved_and_sorted_last(self) -> None:
        """分类同步应保留人工填写的其他，并将其排在全量表现有体系之后。"""
        other_rule = {
            "组织体系": "其他",
            "机构类型": "",
            "机构名称": "待分类机构",
            "领导链接": "https://other.example/",
            "脚本序号": "0002",
        }
        other_match = explicit_other_classification(other_rule)
        self.assertIsNotNone(other_match)
        assert other_match is not None
        existing_rule = {
            "组织体系": "央企",
            "机构类型": "中央企业",
            "机构名称": "某央企",
            "领导链接": "https://example.com/",
            "脚本序号": "0001",
        }
        matches = {
            "0001": MatchResult(
                "央企", "中央企业", "某央企", "测试", "自动通过", "高", ""
            ),
            "0002": other_match,
        }
        full_records = [
            FullRecord("央企", "中央企业", "某央企", "https://example.com/", "")
        ]

        sorted_rows, audit_rows = sort_rules_by_full_table(
            [existing_rule, other_rule], matches, full_records
        )

        self.assertEqual([row["脚本序号"] for row in sorted_rows], ["0001", "0002"])
        self.assertEqual(audit_rows[1]["排序依据"], "机构全量表外体系末尾")

    def test_non_business_note_is_rejected(self) -> None:
        """适配器改造等过程性备注不得重新写入规则主表。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "市局领导\t\t\t\t河北省\t石家庄市\t石家庄教育局\t\t\thttps://example.com/\t0001\t适配器改造A\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "非业务备注"):
                load_rule_table(source_path)

    def test_empty_alias_is_accepted(self) -> None:
        """没有已确认别称的机构允许将别称留空。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "其他\t\t\t\t全国\t\t待分类机构\t\t\thttps://example.com/\t0001\t\n",
                encoding="utf-8",
            )

            records = load_rule_table(source_path)

        self.assertEqual(records[0]["机构别称"], "")

    def test_alias_rejects_non_ideographic_separator(self) -> None:
        """多个别称必须使用中文顿号，不能混用逗号等分隔符。"""
        with TemporaryDirectory() as temporary_dir:
            source_path = Path(temporary_dir) / "规则主表.txt"
            source_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "其他\t\t\t\t全国\t\t待分类机构\t简称一，简称二\t\thttps://example.com/\t0001\t\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "必须使用中文顿号分隔"):
                load_rule_table(source_path)

    def test_alias_rejects_duplicate_or_canonical_name(self) -> None:
        """别称不得重复，也不得再次填写机构名称。"""
        with TemporaryDirectory() as temporary_dir:
            duplicate_path = Path(temporary_dir) / "重复别称.txt"
            duplicate_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "其他\t\t\t\t全国\t\t待分类机构\t简称、简称\t\thttps://example.com/\t0001\t\n",
                encoding="utf-8",
            )
            canonical_path = Path(temporary_dir) / "机构名称重复.txt"
            canonical_path.write_text(
                "组织体系\t目录链接\t机构类型\t机构层级\t所属省*\t所属市\t机构名称\t机构别称\t官网链接\t领导链接\t脚本序号\t备注\n"
                "其他\t\t\t\t全国\t\t待分类机构\t待分类机构\t\thttps://example.com/\t0001\t\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "别称含重复项"):
                load_rule_table(duplicate_path)
            with self.assertRaisesRegex(ValueError, "别称不得重复机构名称"):
                load_rule_table(canonical_path)
