from pathlib import Path

from workspace.institution_catalog.maintenance.build_provincial_government_inventory_and_missing import (
    compare_with_rule_table,
)
from workspace.institution_catalog.maintenance.fill_official_urls_from_leader_urls import (
    fill_official_urls,
)
from workspace.institution_catalog.maintenance.prepare_link_research_batches import (
    split_blank_official_rows,
)
from workspace.institution_catalog.maintenance.table_io import INSTITUTION_HEADERS, read_table


def _row(**values: str) -> list[str]:
    return [values.get(header, "") for header in INSTITUTION_HEADERS]


def test_migrated_master_uses_twelve_field_contract() -> None:
    path = Path(__file__).resolve().parents[1] / "source_data" / "机构主表.txt"
    headers, rows = read_table(path)
    assert headers == INSTITUTION_HEADERS
    assert rows


def test_fill_official_urls_preserves_all_other_fields() -> None:
    original = _row(机构名称="测试机构", 领导链接="https://example.gov.cn/leader/list")
    updated, filled, skipped = fill_official_urls(INSTITUTION_HEADERS, [original])
    official_index = INSTITUTION_HEADERS.index("官网链接")
    assert updated[0][official_index] == "https://example.gov.cn/"
    assert updated[0][:official_index] == original[:official_index]
    assert updated[0][official_index + 1 :] == original[official_index + 1 :]
    assert (filled, skipped) == (1, 0)


def test_link_batches_keep_source_order_and_all_twelve_fields() -> None:
    rows = [
        _row(机构名称="甲"),
        _row(机构名称="乙", 官网链接="https://b.example/"),
        _row(机构名称="丙"),
    ]
    batches = split_blank_official_rows(INSTITUTION_HEADERS, rows, 2)
    name_index = INSTITUTION_HEADERS.index("机构名称")
    assert [[row[name_index] for row in batch] for batch in batches] == [["甲"], ["丙"]]
    assert all(len(row) == 12 for batch in batches for row in batch)


def test_provincial_comparison_reads_new_rule_fields() -> None:
    inventory = [
        {
            "区域": "安徽省人民政府",
            "目录链接": "https://www.ah.gov.cn/directory",
            "机构大类名称": "组成部门",
            "机构小类名称": "安徽省教育厅",
            "机构链接": "https://jyt.ah.gov.cn/",
        }
    ]
    rules = [
        {
            "所属省*": "安徽省",
            "机构名称": "安徽省教育厅",
            "官网链接": "https://jyt.ah.gov.cn/",
            "领导链接": "https://jyt.ah.gov.cn/leader/",
            "脚本序号": "0001",
        }
    ]
    missing, audit = compare_with_rule_table(inventory, rules)
    assert missing == []
    assert audit[0]["规则主表机构"] == "安徽省教育厅"
    assert audit[0]["脚本序号"] == "0001"
    assert audit[0]["官网链接"] == "https://jyt.ah.gov.cn/"
