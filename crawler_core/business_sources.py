from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from crawler_core.rule_table import DEFAULT_RULE_TABLE_PATH, load_rule_table, normalize_script_sequence


DEFAULT_SOURCE_PATH = DEFAULT_RULE_TABLE_PATH


@dataclass(frozen=True)
class BusinessSource:
    """只读业务源记录。"""

    script_sequence: str
    organization: str
    source_url: str
    province: str = ""
    city: str = ""
    aliases: tuple[str, ...] = ()
    note: str = ""


def load_business_sources(path: Path | None = None) -> dict[str, BusinessSource]:
    """读取权威规则主表；不修改源文件。"""
    sources: dict[str, BusinessSource] = {}
    for record in load_rule_table(path):
        sequence = record["脚本序号"]
        sources[sequence] = BusinessSource(
            script_sequence=sequence,
            organization=record["机构名称"],
            source_url=record["领导链接"],
            province=record["所属省*"],
            city=record["所属市"],
            aliases=tuple(item for item in record["机构别称"].split("、") if item),
            note=record["备注"],
        )
    return sources


def get_business_source(script_sequence: object, path: Path | None = None) -> BusinessSource:
    """按脚本序号读取权威业务源。"""
    sequence = normalize_script_sequence(script_sequence)
    source = load_business_sources(path).get(sequence)
    if source is None:
        raise KeyError(f"规则主表未登记脚本序号：{sequence}")
    return source


def apply_business_source(rule: dict, path: Path | None = None) -> dict:
    """在规则副本上注入权威机构名称、领导链接和地区，原字典保持不变。"""
    sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence"))
    if not sequence:
        return dict(rule)
    source = get_business_source(sequence, path)
    resolved = dict(rule)
    resolved["rule_id"] = sequence
    resolved["organization"] = source.organization
    resolved["url"] = source.source_url
    resolved["province"] = source.province
    resolved["city"] = source.city
    resolved["organization_aliases"] = source.aliases
    resolved["business_source_note"] = source.note
    return resolved
