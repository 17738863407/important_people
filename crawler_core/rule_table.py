from __future__ import annotations

from pathlib import Path


RULE_TABLE_REQUIRED_FIELDS = (
    "脚本序号",
    "机构名称",
)
RULE_TABLE_OPTIONAL_DEFAULTS = (
    "目录链接",
    "所属省*",
    "所属市",
    "机构别称",
    "官网链接",
    "备注",
)
# 保留既有常量名，供所有主表读写方共享严格字段顺序。
RULE_TABLE_FIELDS = (
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
)
RULE_TABLE_ALLOWED_NOTES = {"", "空缺占位", "两个机构一块牌子"}
RULE_TABLE_ALLOWED_ORGANIZATION_SYSTEMS = {
    "",
    "中共中央",
    "全国人大",
    "国务院",
    "全国政协",
    "最高人民法院",
    "最高人民检察院",
    "法院",
    "检察院",
    "纪委监委",
    "民主党派",
    "群团组织",
    "省级四大",
    "省厅领导",
    "地级四大",
    "市局领导",
    "央企",
    "其他",
}
DEFAULT_RULE_TABLE_PATH = (
    Path(__file__).resolve().parents[1] / "workspace" / "source_data" / "规则主表.txt"
)


def normalize_script_sequence(value: object) -> str:
    """把 RULE_0001、1 等形式统一为四位脚本序号。"""
    text = str(value or "").strip()
    if text.upper().startswith("RULE_"):
        text = text[5:]
    return text.zfill(4) if text else ""


def load_rule_table(path: Path | None = None) -> list[dict[str, str]]:
    """读取权威主表，并严格校验十二列字段及记录级机构别称。"""
    source_path = path or DEFAULT_RULE_TABLE_PATH
    lines = source_path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"规则主表为空：{source_path}")

    header = tuple(lines[0].split("\t"))
    if not all(header) or len(header) != len(set(header)):
        raise ValueError(f"规则主表表头含空字段或重复字段：{source_path}")
    missing_fields = [field for field in RULE_TABLE_REQUIRED_FIELDS if field not in header]
    if missing_fields:
        raise ValueError(
            f"规则主表缺少核心字段：{', '.join(missing_fields)}：{source_path}"
        )
    if header != RULE_TABLE_FIELDS:
        raise ValueError(f"规则主表表头不符合十二列顺序契约：{source_path}")

    records: list[dict[str, str]] = []
    seen_sequences: set[str] = set()
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        values = line.split("\t")
        if len(values) != len(header):
            raise ValueError(f"规则主表第 {line_number} 行列数错误：{source_path}")
        record = {
            field: value.strip()
            for field, value in zip(header, values)
        }
        for field in RULE_TABLE_OPTIONAL_DEFAULTS:
            record.setdefault(field, "")
        sequence = normalize_script_sequence(record["脚本序号"])
        if not sequence or not record["机构名称"]:
            raise ValueError(f"规则主表第 {line_number} 行缺少必填值：{source_path}")
        if sequence in seen_sequences:
            raise ValueError(f"规则主表脚本序号重复：{sequence}")
        if record["备注"] not in RULE_TABLE_ALLOWED_NOTES:
            raise ValueError(f"规则主表第 {line_number} 行含非业务备注：{record['备注']}")
        aliases = record["机构别称"]
        if any(separator in aliases for separator in (",", "，", ";", "；", "/")):
            raise ValueError(
                f"规则主表第 {line_number} 行别称必须使用中文顿号分隔：{aliases}"
            )
        alias_items = [item.strip() for item in aliases.split("、")] if aliases else []
        if any(not item for item in alias_items):
            raise ValueError(f"规则主表第 {line_number} 行别称含空项：{aliases}")
        if len(alias_items) != len(set(alias_items)):
            raise ValueError(f"规则主表第 {line_number} 行别称含重复项：{aliases}")
        if record["机构名称"] in alias_items:
            raise ValueError(
                f"规则主表第 {line_number} 行别称不得重复机构名称：{record['机构名称']}"
            )
        organization_system = record.get("组织体系", "")
        if organization_system not in RULE_TABLE_ALLOWED_ORGANIZATION_SYSTEMS:
            raise ValueError(
                f"规则主表第 {line_number} 行组织体系不在允许范围：{organization_system}"
            )
        record["脚本序号"] = sequence
        seen_sequences.add(sequence)
        records.append(record)
    return records


def to_generation_record(record: dict[str, str]) -> dict[str, object]:
    """补充工具兼容列名，并原样保留主表中的全部扩展字段。"""
    generation_record: dict[str, object] = dict(record)
    generation_record.update({
        "规则ID": f"RULE_{record['脚本序号']}",
        "机构": record["机构名称"],
        "领导信息链接": record["领导链接"],
    })
    return generation_record


def load_generation_records(path: Path | None = None) -> list[dict[str, object]]:
    """读取全部业务记录；不再提供页面技术画像。"""
    return [to_generation_record(record) for record in load_rule_table(path)]
