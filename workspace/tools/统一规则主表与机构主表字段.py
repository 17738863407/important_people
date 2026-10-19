"""把规则主表和机构主表分别迁移为统一的十二列字段契约。"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

try:
    from crawler_core.paths import resolve_external_path, resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_external_path, resolve_project_path


UNIFIED_FIELDS = (
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
LEGACY_RULE_FIELDS = (
    "组织体系",
    "机构类型",
    "机构层级",
    "所属省*",
    "所属市",
    "机构名称",
    "别称",
    "领导链接",
    "脚本序号",
    "备注",
)
LEGACY_INSTITUTION_FIELDS = (
    "组织体系",
    "目录链接",
    "机构类型",
    "机构名称",
    "官网链接",
    "领导链接",
    "主表匹配",
)


def configure_logger(log_path: Path) -> logging.Logger:
    """创建同时输出到控制台和文件的日志器。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("unify_master_table_fields")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def clean(value: object) -> str:
    """清除字段两端空白及不可见字符。"""
    return str(value or "").replace("\ufeff", "").replace("\u200b", "").strip()


def read_tsv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]], int]:
    """严格读取制表符文本，并统计被忽略的全空行。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"文件为空：{path}")
    fields = tuple(clean(value) for value in lines[0].split("\t"))
    if not all(fields) or len(fields) != len(set(fields)):
        raise ValueError(f"表头含空字段或重复字段：{path}")
    rows: list[dict[str, str]] = []
    blank_count = 0
    for line_number, line in enumerate(lines[1:], start=2):
        values = line.split("\t")
        if not line.strip() or all(not clean(value) for value in values):
            blank_count += 1
            continue
        if len(values) != len(fields):
            raise ValueError(
                f"{path.name}第{line_number}行字段数为{len(values)}，应为{len(fields)}"
            )
        rows.append({field: clean(value) for field, value in zip(fields, values, strict=True)})
    return fields, rows, blank_count


def render_tsv(rows: list[dict[str, str]]) -> bytes:
    """按统一字段顺序生成 UTF-8 BOM 制表符文本。"""
    lines = ["\t".join(UNIFIED_FIELDS)]
    for row in rows:
        values = [clean(row.get(field, "")) for field in UNIFIED_FIELDS]
        if any("\t" in value or "\r" in value or "\n" in value for value in values):
            raise ValueError(f"字段含制表符或换行，无法安全写出：{row.get('机构名称', '')}")
        lines.append("\t".join(values))
    return ("\ufeff" + "\n".join(lines) + "\n").encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    """先写同目录临时文件，校验后原子替换正式文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_bytes(content)
    fields, _, _ = read_tsv(temporary_path)
    if fields != UNIFIED_FIELDS:
        raise ValueError(f"写出后的字段顺序校验失败：{path}")
    os.replace(temporary_path, path)


def normalized_url(value: str) -> tuple[str, str, str, str, str]:
    """构造保留协议、查询参数和片段，仅统一www与尾斜杠的链接键。"""
    parsed = urlsplit(clean(value))
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/").lower()
    return scheme, host, path, parsed.query, parsed.fragment


def migrate_rule_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """将十列规则主表迁移为十二列，但不改变任何原业务值。"""
    output: list[dict[str, str]] = []
    for row in rows:
        output.append(
            {
                "组织体系": row["组织体系"],
                "目录链接": "",
                "机构类型": row["机构类型"],
                "机构层级": row["机构层级"],
                "所属省*": row["所属省*"],
                "所属市": row["所属市"],
                "机构名称": row["机构名称"],
                "机构别称": row["别称"],
                "官网链接": "",
                "领导链接": row["领导链接"],
                "脚本序号": row["脚本序号"].zfill(4),
                "备注": row["备注"],
            }
        )
    return output


def build_rule_indexes(
    rule_rows: list[dict[str, str]],
) -> tuple[
    dict[str, list[dict[str, str]]],
    dict[tuple[str, str, str, str, str], list[dict[str, str]]],
]:
    """建立机构名称和领导链接索引；别称不参与自动写入，避免宽松误配。"""
    name_index: dict[str, list[dict[str, str]]] = defaultdict(list)
    url_index: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rule_rows:
        name_index[row["机构名称"]].append(row)
        url_key = normalized_url(row["领导链接"])
        if url_key[1]:
            url_index[url_key].append(row)
    return name_index, url_index


def resolve_rule(
    institution: dict[str, str],
    name_index: dict[str, list[dict[str, str]]],
    url_index: dict[tuple[str, str, str, str, str], list[dict[str, str]]],
) -> tuple[dict[str, str] | None, str, list[dict[str, str]]]:
    """按机构名称精确匹配优先、领导链接唯一匹配次之确定规则记录。"""
    name_matches = name_index.get(institution["机构名称"], [])
    if len(name_matches) == 1:
        return name_matches[0], "机构名称精确匹配", name_matches
    url_key = normalized_url(institution["领导链接"])
    url_matches = url_index.get(url_key, []) if url_key[1] else []
    if len(url_matches) == 1:
        return url_matches[0], "领导链接唯一匹配", url_matches
    candidates = name_matches or url_matches
    reason = "领导链接对应多个脚本序号" if len(candidates) > 1 else "未匹配"
    return None, reason, candidates


def migrate_institution_rows(
    rows: list[dict[str, str]], rule_rows: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    """迁移机构主表，并为唯一命中的记录补入规则主表字段。"""
    name_index, url_index = build_rule_indexes(rule_rows)
    output: list[dict[str, str]] = []
    audit: list[dict[str, str]] = []
    stats: dict[str, int] = defaultdict(int)
    for source_line, row in enumerate(rows, start=2):
        matched, method, candidates = resolve_rule(row, name_index, url_index)
        old_mark = row["主表匹配"]
        if matched is None:
            stats[f"旧{old_mark or '空'}但无法确定"] += 1
        else:
            stats[f"旧{old_mark or '空'}且已确定"] += 1
            stats[method] += 1
        output.append(
            {
                "组织体系": row["组织体系"],
                "目录链接": row["目录链接"],
                "机构类型": row["机构类型"],
                "机构层级": matched["机构层级"] if matched else "",
                "所属省*": matched["所属省*"] if matched else "",
                "所属市": matched["所属市"] if matched else "",
                "机构名称": row["机构名称"],
                "机构别称": matched["机构别称"] if matched else "",
                "官网链接": row["官网链接"],
                "领导链接": row["领导链接"],
                "脚本序号": matched["脚本序号"] if matched else "",
                "备注": matched["备注"] if matched else "",
            }
        )
        if (old_mark == "有" and matched is None) or (old_mark == "无" and matched is not None):
            audit.append(
                {
                    "机构主表行号": str(source_line),
                    "机构名称": row["机构名称"],
                    "领导链接": row["领导链接"],
                    "旧主表匹配": old_mark,
                    "迁移后脚本序号": matched["脚本序号"] if matched else "",
                    "判定": method,
                    "候选脚本序号": "、".join(item["脚本序号"] for item in candidates),
                    "候选规则机构": "｜".join(item["机构名称"] for item in candidates),
                }
            )
    return output, audit, dict(stats)


def render_audit(rows: list[dict[str, str]]) -> bytes:
    """生成旧标记与脚本序号判断不一致的迁移审计。"""
    fields = (
        "机构主表行号",
        "机构名称",
        "领导链接",
        "旧主表匹配",
        "迁移后脚本序号",
        "判定",
        "候选脚本序号",
        "候选规则机构",
    )
    lines = ["\t".join(fields)]
    lines.extend("\t".join(clean(row[field]) for field in fields) for row in rows)
    return ("\ufeff" + "\n".join(lines) + "\n").encode("utf-8")


def file_hash(path: Path) -> str:
    """计算文件 SHA-256。"""
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main(
    rule_table_path: str | Path,
    institution_table_path: Path,
    rule_backup_dir: str | Path,
    institution_backup_dir: Path,
    audit_path: str | Path,
    log_path: str | Path,
) -> None:
    """备份、迁移、写出并复核两张主表。"""
    resolved_rule_path = resolve_project_path(rule_table_path, anchor=__file__, must_exist=True)
    resolved_rule_backup_dir = resolve_project_path(rule_backup_dir, anchor=__file__)
    resolved_audit_path = resolve_project_path(audit_path, anchor=__file__)
    resolved_log_path = resolve_project_path(log_path, anchor=__file__)
    logger = configure_logger(resolved_log_path)
    rule_fields, legacy_rules, rule_blank_count = read_tsv(resolved_rule_path)
    institution_fields, institutions, institution_blank_count = read_tsv(institution_table_path)
    if rule_fields != LEGACY_RULE_FIELDS:
        raise ValueError(f"规则主表不是预期十列结构：{rule_fields}")
    if institution_fields != LEGACY_INSTITUTION_FIELDS:
        raise ValueError(f"机构主表不是预期七列结构：{institution_fields}")

    migrated_rules = migrate_rule_rows(legacy_rules)
    migrated_institutions, audit_rows, stats = migrate_institution_rows(
        institutions, migrated_rules
    )
    if len({row["脚本序号"] for row in migrated_rules}) != len(migrated_rules):
        raise ValueError("规则主表迁移后脚本序号不唯一")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    resolved_rule_backup_dir.mkdir(parents=True, exist_ok=True)
    institution_backup_dir.mkdir(parents=True, exist_ok=True)
    rule_backup = resolved_rule_backup_dir / f"规则主表-统一十二列前-{timestamp}.txt"
    institution_backup = institution_backup_dir / f"机构主表-统一十二列前-{timestamp}.txt"
    shutil.copy2(resolved_rule_path, rule_backup)
    shutil.copy2(institution_table_path, institution_backup)

    atomic_write(resolved_rule_path, render_tsv(migrated_rules))
    atomic_write(institution_table_path, render_tsv(migrated_institutions))
    resolved_audit_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_audit_path.write_bytes(render_audit(audit_rows))

    verify_rule_fields, verify_rules, _ = read_tsv(resolved_rule_path)
    verify_institution_fields, verify_institutions, _ = read_tsv(institution_table_path)
    if verify_rule_fields != UNIFIED_FIELDS or verify_institution_fields != UNIFIED_FIELDS:
        raise ValueError("迁移后字段契约复核失败")
    if len(verify_rules) != len(legacy_rules) or len(verify_institutions) != len(institutions):
        raise ValueError("迁移前后有效记录数不一致")

    logger.info("规则主表：%s 条；忽略全空行 %s 条", len(verify_rules), rule_blank_count)
    logger.info("机构主表：%s 条；忽略全空行 %s 条", len(verify_institutions), institution_blank_count)
    for key, value in sorted(stats.items()):
        logger.info("%s：%s 条", key, value)
    logger.info("差异审计：%s 条 -> %s", len(audit_rows), resolved_audit_path)
    logger.info("规则主表备份：%s", rule_backup)
    logger.info("机构主表备份：%s", institution_backup)
    logger.info("规则主表 SHA256：%s", file_hash(resolved_rule_path))
    logger.info("机构主表 SHA256：%s", file_hash(institution_table_path))


if __name__ == "__main__":
    input_rule_table_path = r"important_people/workspace/source_data/规则主表.txt"
    external_catalog_dir = resolve_external_path("IMPORTANT_PERSON_ORGANIZATION_CATALOG_DIR")
    input_institution_table_path = external_catalog_dir / "机构全表.txt"
    output_rule_backup_dir = r"important_people/workspace/source_data/backup/规则主表"
    output_institution_backup_dir = external_catalog_dir / "backup" / "schema_migration"
    output_audit_path = r"important_people/workspace/reports/机构主表十二列字段迁移审计.txt"
    output_log_path = r"important_people/workspace/log/统一规则主表与机构主表字段.log"
    main(
        input_rule_table_path,
        input_institution_table_path,
        output_rule_backup_dir,
        output_institution_backup_dir,
        output_audit_path,
        output_log_path,
    )
