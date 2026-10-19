"""把机构全量表中的组织体系、机构类型同步到重要人物规则主表。"""

from __future__ import annotations

import codecs
import logging
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from tqdm import tqdm

try:
    from workspace.tools.project_paths import resolve_project_path, timestamped_output_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path, timestamped_output_path


@dataclass(frozen=True)
class FullRecord:
    """机构全量表中参与分类匹配的最小记录。"""

    organization_system: str
    institution_type: str
    institution_name: str
    leader_url: str
    script_sequence: str

    @property
    def pair(self) -> tuple[str, str]:
        return self.organization_system, self.institution_type


@dataclass(frozen=True)
class MatchResult:
    """单条规则主表记录的分类匹配结果。"""

    organization_system: str
    institution_type: str
    source_names: str
    method: str
    review_status: str
    confidence: str
    note: str


def clean_field(value: object) -> str:
    """清除字段两端空白及零宽字符。"""
    return str(value or "").replace("\ufeff", "").replace("\u200b", "").strip()


def rule_name(rule: dict[str, str]) -> str:
    """兼容迁移前后的机构名称字段。"""
    return clean_field(rule.get("机构名称") or rule.get("机构"))


def rule_leader_url(rule: dict[str, str]) -> str:
    """兼容迁移前后的领导链接字段。"""
    return clean_field(rule.get("领导链接") or rule.get("依据链接"))


def configure_logger(log_path: Path) -> logging.Logger:
    """建立同时写入控制台和日志文件的日志器。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sync_institution_classification")
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


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """严格读取UTF-8制表符文本，并校验逐行列数。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"文件为空：{path}")
    headers = [clean_field(value) for value in lines[0].split("\t")]
    if not all(headers) or len(headers) != len(set(headers)):
        raise ValueError(f"表头存在空字段或重复字段：{path}")
    records: list[dict[str, str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        values = line.split("\t")
        if len(values) != len(headers):
            raise ValueError(
                f"{path.name}第{line_number}行字段数为{len(values)}，应为{len(headers)}"
            )
        records.append(
            {header: clean_field(value) for header, value in zip(headers, values, strict=True)}
        )
    return headers, records


def normalized_url_key(url: str) -> tuple[str, str]:
    """生成忽略协议、www、查询参数、片段和尾斜杠的保守URL键。"""
    parsed = urlparse(clean_field(url))
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", parsed.path).rstrip("/").lower()
    return host, path


def normalized_name(value: str, drop_parenthetical: bool = False) -> str:
    """沿用机构大全项目的机构名称规范键。"""
    text = clean_field(value)
    if drop_parenthetical:
        text = re.sub(r"[（(][^（）()]*[）)]", "", text)
    replacements = (
        ("中国共产党中央委员会", "中共中央"),
        ("全国人民代表大会常务委员会", "全国人大常委会"),
        ("全国人民代表大会", "全国人大"),
        ("中国人民政治协商会议全国委员会", "全国政协"),
        ("教育科学文化卫生", "教科文卫"),
    )
    for source_text, target_text in replacements:
        text = text.replace(source_text, target_text)
    text = text.replace("中国共产党", "中共")
    return re.sub(r"[\s\u200b\ufeff·•。:：;；,，、\-—_/（）()]", "", text)


def institution_name_keys(record: FullRecord) -> set[str]:
    """从机构全量表记录构造其标准名称及带上级前缀的名称键。"""
    raw_candidates = {record.institution_name}
    if "-" in record.institution_type:
        parent_name = record.institution_type.split("-", maxsplit=1)[0]
        if parent_name:
            raw_candidates.add(
                record.institution_name
                if record.institution_name.startswith(parent_name)
                else f"{parent_name}{record.institution_name}"
            )
    if record.institution_name.endswith("党委"):
        region = record.institution_name.removesuffix("党委")
        raw_candidates.update({f"{region}委", f"中共{region}委", f"中国共产党{region}委员会"})
    elif record.institution_name.endswith("人大"):
        region = record.institution_name.removesuffix("人大")
        raw_candidates.update(
            {f"{region}人大常委会", f"{region}人民代表大会常务委员会", f"{region}人民代表大会"}
        )
    elif record.institution_name.endswith("政协"):
        region = record.institution_name.removesuffix("政协")
        raw_candidates.update({f"{region}政协委员会", f"中国人民政治协商会议{region}委员会"})
    keys: set[str] = set()
    for candidate in raw_candidates:
        keys.add(normalized_name(candidate))
        keys.add(normalized_name(candidate, drop_parenthetical=True))
    keys.discard("")
    return keys


def unique_records(records: list[FullRecord]) -> list[FullRecord]:
    """按全部分类事实去重，并保持机构全量表首次出现顺序。"""
    output: list[FullRecord] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        key = (*record.pair, record.institution_name, record.leader_url)
        if key not in seen:
            seen.add(key)
            output.append(record)
    return output


def expected_systems(rule: dict[str, str]) -> set[str]:
    """仅用于多候选消歧，不据此凭空创造机构类型。"""
    current_system = rule.get("组织体系", "")
    if current_system:
        return {current_system}
    category = rule.get("机构大类", "")
    subcategory = rule.get("机构小类", "")
    province = rule.get("所属省*", "")
    city = rule.get("所属市", "")
    name = rule_name(rule)
    national = province == "全国"
    if category == "党委":
        return {"中共中央"} if national else {"地级四大" if city else "省级四大"}
    if category == "人大":
        return {"全国人大"} if national else {"地级四大" if city else "省级四大"}
    if category == "政协":
        return {"全国政协"} if national else {"地级四大" if city else "省级四大"}
    if category == "政府":
        if national:
            return {"国务院"}
        is_government_head = name.endswith("人民政府") or name.endswith("政府")
        if city:
            return {"地级四大" if is_government_head else "市局领导"}
        return {"省级四大" if is_government_head else "省厅领导"}
    if category == "法院":
        return {"最高人民法院"}
    if category == "检察院":
        return {"最高人民检察院"}
    if category == "民主党派、社会团体":
        if subcategory == "八大民主党派":
            return {"民主党派"}
        if subcategory.startswith("22个群团组织"):
            return {"群团组织"}
    if "公司" in name or "集团" in name:
        return {"央企"}
    return set()


def resolve_candidates(
    records: list[FullRecord], rule: dict[str, str], method: str
) -> MatchResult | None:
    """在候选分类中优先选择唯一分类，再依据旧地区口径消除多目录冲突。"""
    candidates = unique_records(records)
    pairs = {record.pair for record in candidates}
    if not pairs:
        return None
    if len(pairs) == 1:
        selected_pair = next(iter(pairs))
        source_names = "；".join(dict.fromkeys(record.institution_name for record in candidates))
        return MatchResult(*selected_pair, source_names, method, "自动通过", "高", "候选分类唯一")

    expected = expected_systems(rule)
    expected_records = [record for record in candidates if record.organization_system in expected]
    expected_pairs = {record.pair for record in expected_records}
    if len(expected_pairs) == 1:
        selected_pair = next(iter(expected_pairs))
        source_names = "；".join(
            dict.fromkeys(record.institution_name for record in expected_records)
        )
        return MatchResult(
            *selected_pair,
            source_names,
            f"{method}+地区体系消歧",
            "自动通过",
            "高",
            f"多目录候选按既有地区和机构属性选择{selected_pair[0]}",
        )
    return None


def build_indexes(full_records: list[FullRecord]) -> dict[str, dict[object, list[FullRecord]]]:
    """建立原名、规范名、领导链接和机构类型上级名称索引。"""
    raw_name_index: dict[object, list[FullRecord]] = defaultdict(list)
    normalized_name_index: dict[object, list[FullRecord]] = defaultdict(list)
    url_index: dict[object, list[FullRecord]] = defaultdict(list)
    parent_index: dict[object, list[FullRecord]] = defaultdict(list)
    for record in full_records:
        raw_name_index[record.institution_name].append(record)
        for key in institution_name_keys(record):
            normalized_name_index[key].append(record)
        url_key = normalized_url_key(record.leader_url)
        if url_key[0]:
            url_index[url_key].append(record)
        if "-" in record.institution_type:
            parent = record.institution_type.split("-", maxsplit=1)[0]
            parent_index[normalized_name(parent)].append(record)
    return {
        "raw": raw_name_index,
        "normalized": normalized_name_index,
        "url": url_index,
        "parent": parent_index,
    }


def build_audit_index(
    audit_records: list[dict[str, str]],
    url_index: dict[object, list[FullRecord]],
) -> dict[str, list[FullRecord]]:
    """把省厅审计报告中已明确的脚本序号回连到机构全量表分类。"""
    output: dict[str, list[FullRecord]] = defaultdict(list)
    for record in audit_records:
        sequence = clean_field(record.get("脚本序号", "")).zfill(4)
        if record.get("匹配状态") != "已记录" or not sequence.strip("0"):
            continue
        url_key = normalized_url_key(record.get("机构链接", ""))
        output[sequence].extend(url_index.get(url_key, []))
    return output


def load_manual_overrides(mapping_path: Path) -> dict[str, MatchResult]:
    """读取既有映射表中已经人工确认的分类，防止后续自动同步覆盖。"""
    if not mapping_path.exists():
        return {}
    _, records = read_tsv(mapping_path)
    output: dict[str, MatchResult] = {}
    for record in records:
        if record.get("复核状态") != "人工通过" or not record.get("组织体系"):
            continue
        sequence = record.get("脚本序号", "").zfill(4)
        output[sequence] = MatchResult(
            record["组织体系"],
            record.get("机构类型", ""),
            record.get("机构全量表机构名称", ""),
            "保留人工确认映射",
            "人工通过",
            "高",
            record.get("备注", ""),
        )
    return output


def explicit_other_classification(rule: dict[str, str]) -> MatchResult | None:
    """保留规则主表中人工指定的“其他”体系，避免同步时被自动分类覆盖。"""
    if clean_field(rule.get("组织体系")) != "其他":
        return None
    return MatchResult(
        "其他",
        clean_field(rule.get("机构类型")),
        "",
        "规则主表明确标记",
        "人工通过",
        "高",
        "现有组织体系无法有效分类，保留规则主表人工指定值",
    )


def parent_name_candidates(name: str) -> list[str]:
    """为分页面名称生成保守的上级机构名称候选。"""
    candidates = [name]
    for separator in ("-", "—"):
        if separator in name:
            candidates.append(name.split(separator, maxsplit=1)[0])
    candidates.append(
        re.sub(r"[（(][^（）()]*(?:领导|委员|秘书处|董事会)[^（）()]*[）)]$", "", name)
    )
    return list(dict.fromkeys(clean_field(candidate) for candidate in candidates if clean_field(candidate)))


def fuzzy_match(
    rule: dict[str, str], full_records: list[FullRecord]
) -> MatchResult | None:
    """对仍未命中的记录执行受组织体系约束的高阈值名称匹配。"""
    expected = expected_systems(rule)
    pool = [record for record in full_records if not expected or record.organization_system in expected]
    target = normalized_name(rule_name(rule), drop_parenthetical=True)
    scored: list[tuple[float, FullRecord]] = []
    for record in pool:
        candidate = normalized_name(record.institution_name, drop_parenthetical=True)
        if not target or not candidate:
            continue
        score = SequenceMatcher(None, target, candidate).ratio()
        if target in candidate or candidate in target:
            score += 0.08
        scored.append((score, record))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score = scored[0][0]
    best_records = [record for score, record in scored if abs(score - best_score) < 0.000001]
    second_score = next((score for score, _ in scored if score < best_score - 0.000001), 0.0)
    if best_score < 0.93 or best_score - second_score < 0.05:
        return None
    resolved = resolve_candidates(best_records, rule, "高阈值名称相似")
    if resolved is None:
        return None
    return MatchResult(
        resolved.organization_system,
        resolved.institution_type,
        resolved.source_names,
        resolved.method,
        "自动通过",
        "高",
        f"名称相似度{best_score:.4f}，与次优差值{best_score - second_score:.4f}",
    )


def source_system_fallback(
    rule: dict[str, str], parent_records: list[FullRecord]
) -> MatchResult | None:
    """源表缺少机构本身记录时，只填写能够由目录结构确认的组织体系。"""
    parent_systems = {record.organization_system for record in parent_records}
    if len(parent_systems) == 1:
        selected_system = next(iter(parent_systems))
        return MatchResult(
            selected_system,
            "",
            "",
            "机构类型上级目录",
            "源表无直接机构类型",
            "高",
            "机构全量表仅收录其下级目录，组织体系可确认，机构类型无直接对应值",
        )

    expected = expected_systems(rule)
    if not expected:
        category = rule.get("机构大类", "")
        province = rule.get("所属省*", "")
        city = rule.get("所属市", "")
        name = rule_name(rule)
        if category == "直属事业单位、大学及其他":
            expected = {"市局领导" if city else "省厅领导" if province != "全国" else "国务院"}
        elif category == "民主党派、社会团体":
            if "青年联合会" in name:
                expected = {"群团组织"}
            elif city:
                expected = {"市局领导"}
            elif province != "全国":
                expected = {"省厅领导"}
            else:
                expected = {"国务院"}
        elif "市委书记、市长、政协主席、人大常委会主任" in name:
            expected = {"地级四大"}
    if len(expected) != 1:
        return None
    selected_system = next(iter(expected))
    return MatchResult(
        selected_system,
        "",
        "",
        "源表体系口径补录",
        "源表无直接机构类型",
        "中",
        "机构全量表无该机构直接记录；依据同地区、同类目录的组织体系补录，机构类型留空",
    )


def match_rule(
    rule: dict[str, str],
    indexes: dict[str, dict[object, list[FullRecord]]],
    audit_index: dict[str, list[FullRecord]],
    full_records: list[FullRecord],
) -> MatchResult:
    """按审计、原名、规范名、链接、上级目录和高阈值相似度依次匹配。"""
    sequence = rule["脚本序号"].zfill(4)
    attempts: list[tuple[str, list[FullRecord]]] = []
    attempts.append(("既有审计", audit_index.get(sequence, [])))
    name = rule_name(rule)
    attempts.append(("机构名称精确", indexes["raw"].get(name, [])))
    normalized_records: list[FullRecord] = []
    for key in {
        normalized_name(name),
        normalized_name(name, drop_parenthetical=True),
    }:
        normalized_records.extend(indexes["normalized"].get(key, []))
    attempts.append(("机构名称规范键", normalized_records))
    attempts.append(("领导链接", indexes["url"].get(normalized_url_key(rule_leader_url(rule)), [])))

    for method, records in attempts:
        resolved = resolve_candidates(records, rule, method)
        if resolved is not None:
            return resolved

    parent_records: list[FullRecord] = []
    for candidate in parent_name_candidates(name):
        parent_records.extend(indexes["raw"].get(candidate, []))
        parent_records.extend(indexes["parent"].get(normalized_name(candidate), []))
    resolved = resolve_candidates(parent_records, rule, "上级机构或目录前缀")
    if resolved is not None:
        return resolved

    system_only = source_system_fallback(rule, parent_records)
    if system_only is not None and parent_records:
        return system_only

    resolved = fuzzy_match(rule, full_records)
    if resolved is not None:
        if (
            rule.get("机构大类") == "政府"
            and rule.get("所属省*") == "全国"
            and re.search(r"(?:部|委员会)$", name)
            and "委员单位" in resolved.institution_type
        ):
            return source_system_fallback(rule, parent_records) or MatchResult(
                "国务院", "", "", "源表体系口径补录", "源表无直接机构类型", "中",
                "机构全量表仅将该机构列为其他目录的委员单位，不作为本机构类型采用",
            )
        return resolved

    system_only = source_system_fallback(rule, parent_records)
    if system_only is not None:
        return system_only

    all_candidates = unique_records([record for _, records in attempts for record in records])
    candidate_text = "；".join(
        dict.fromkeys(
            f"{record.organization_system}/{record.institution_type}/{record.institution_name}"
            for record in all_candidates
        )
    )
    return MatchResult("", "", "", "未自动匹配", "待人工复核", "低", candidate_text)


def write_tsv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    """以UTF-8和制表符格式写出报告。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(headers)]
    for row in rows:
        values = [clean_field(row.get(header, "")).replace("\t", " ").replace("\r", " ").replace("\n", " ") for header in headers]
        lines.append("\t".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def detect_format(path: Path) -> tuple[str, bool, bool]:
    """识别规则主表的换行、BOM和末尾换行格式。"""
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    crlf_count = text.count("\r\n")
    lf_count = text.count("\n") - crlf_count
    newline = "\r\n" if crlf_count >= lf_count else "\n"
    return newline, raw.startswith(codecs.BOM_UTF8), text.endswith(("\r\n", "\n"))


def sort_rules_by_full_table(
    rule_rows: list[dict[str, str]],
    matches: dict[str, MatchResult],
    full_records: list[FullRecord],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """依据机构全量表的物理行序排列规则记录，并生成逐条排序审计。"""
    exact_index: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    url_index: dict[tuple[str, str], list[int]] = defaultdict(list)
    parent_index: dict[tuple[str, str], list[int]] = defaultdict(list)
    system_last_index: dict[str, int] = {}
    for index, record in enumerate(full_records, start=1):
        exact_index[(*record.pair, record.institution_name)].append(index)
        url_key = normalized_url_key(record.leader_url)
        if url_key[0]:
            url_index[url_key].append(index)
        if "-" in record.institution_type:
            parent_name = record.institution_type.split("-", maxsplit=1)[0]
            parent_index[(record.organization_system, normalized_name(parent_name))].append(index)
        system_last_index[record.organization_system] = index

    sort_entries: list[tuple[tuple[int, int, int], dict[str, str], str, int]] = []
    for original_index, rule in enumerate(rule_rows, start=1):
        sequence = rule["脚本序号"].zfill(4)
        match = matches[sequence]
        source_names = [name for name in match.source_names.split("；") if name]
        direct_indexes: list[int] = []
        for source_name in source_names:
            direct_indexes.extend(
                exact_index.get(
                    (match.organization_system, match.institution_type, source_name), []
                )
            )
        if not direct_indexes:
            leader_key = normalized_url_key(rule_leader_url(rule))
            for index in url_index.get(leader_key, []):
                record = full_records[index - 1]
                if record.pair == (match.organization_system, match.institution_type):
                    direct_indexes.append(index)
        if direct_indexes:
            anchor_index = min(direct_indexes)
            anchor_mode = "机构全量表直接行"
            rank = 1
        else:
            parent_indexes = parent_index.get(
                (match.organization_system, normalized_name(rule_name(rule))), []
            )
            if parent_indexes:
                anchor_index = min(parent_indexes)
                anchor_mode = "上级机构目录起始行"
                rank = 0
            else:
                anchor_index = system_last_index.get(
                    match.organization_system,
                    max(system_last_index.values(), default=0),
                )
                if match.organization_system in system_last_index:
                    anchor_mode = "组织体系末尾"
                    rank = 2
                else:
                    anchor_mode = "机构全量表外体系末尾"
                    rank = 3
        sort_entries.append(
            ((anchor_index, rank, original_index), rule, anchor_mode, anchor_index)
        )

    sort_entries.sort(key=lambda item: item[0])
    sorted_rows = [entry[1] for entry in sort_entries]
    original_positions = {
        row["脚本序号"].zfill(4): index for index, row in enumerate(rule_rows, start=1)
    }
    audit_rows: list[dict[str, str]] = []
    for new_index, (_, rule, anchor_mode, anchor_index) in enumerate(sort_entries, start=1):
        sequence = rule["脚本序号"].zfill(4)
        audit_rows.append(
            {
                "原位置": str(original_positions[sequence]),
                "新位置": str(new_index),
                "脚本序号": sequence,
                "机构名称": rule_name(rule),
                "组织体系": matches[sequence].organization_system,
                "机构类型": matches[sequence].institution_type,
                "机构全量表锚点行": str(anchor_index + 1),
                "排序依据": anchor_mode,
            }
        )
    return sorted_rows, audit_rows


def render_rule_table(
    source_path: Path,
    source_rows: list[dict[str, str]],
    matches: dict[str, MatchResult],
) -> bytes:
    """按用户指定的十二列契约生成规则主表。"""
    output_headers = [
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
    output_lines = ["\t".join(output_headers)]
    for row in source_rows:
        match = matches[row["脚本序号"].zfill(4)]
        output_row = {
            "组织体系": match.organization_system,
            "目录链接": row.get("目录链接", ""),
            "机构类型": match.institution_type,
            "机构层级": row.get("机构层级", ""),
            "所属省*": row.get("所属省*", ""),
            "所属市": row.get("所属市", ""),
            "机构名称": rule_name(row),
            "机构别称": row.get("机构别称", ""),
            "官网链接": row.get("官网链接", ""),
            "领导链接": rule_leader_url(row),
            "脚本序号": row["脚本序号"].zfill(4),
            "备注": row.get("备注", ""),
        }
        output_lines.append("\t".join(clean_field(output_row.get(header, "")) for header in output_headers))
    newline, has_bom, has_final_newline = detect_format(source_path)
    text = newline.join(output_lines) + (newline if has_final_newline else "")
    encoded = text.encode("utf-8")
    return codecs.BOM_UTF8 + encoded if has_bom else encoded


def verify_rendered_rule_table(
    output_bytes: bytes,
    source_rows: list[dict[str, str]],
    output_path: Path,
) -> None:
    """回读验证新表字段、记录数、脚本序号及分类完整性。"""
    text = output_bytes.decode("utf-8-sig")
    lines = text.splitlines()
    headers = lines[0].split("\t")
    expected_headers = [
        "组织体系", "目录链接", "机构类型", "机构层级", "所属省*", "所属市",
        "机构名称", "机构别称", "官网链接", "领导链接", "脚本序号", "备注",
    ]
    if headers != expected_headers:
        raise ValueError(f"更新后的规则主表表头不符合十二列契约：{headers}")
    if len(lines) - 1 != len(source_rows):
        raise ValueError("更新后的规则主表记录数发生变化")
    sequence_index = headers.index("脚本序号")
    sequences = [line.split("\t")[sequence_index] for line in lines[1:]]
    if len(sequences) != len(set(sequences)):
        raise ValueError("更新后的规则主表脚本序号重复")
    if not output_path.name.endswith(".txt"):
        raise ValueError("规则主表必须使用.txt扩展名")


def main(
    rule_table_path: Path,
    full_table_path: Path,
    audit_path: Path,
    mapping_report_path: Path,
    pending_report_path: Path,
    sorting_report_path: Path,
    backup_dir: Path,
    log_path: Path,
    apply_changes: bool,
) -> None:
    """完成分类匹配、报告生成、备份、写回和回读验证。"""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pending_report_path = timestamped_output_path(pending_report_path, run_timestamp)
    sorting_report_path = timestamped_output_path(sorting_report_path, run_timestamp)
    log_path = timestamped_output_path(log_path, run_timestamp)
    logger = configure_logger(log_path)
    rule_headers, rule_records = read_tsv(rule_table_path)
    _, full_rows = read_tsv(full_table_path)
    _, audit_records = read_tsv(audit_path)
    required_rule_headers = {"脚本序号"}
    required_full_headers = {"组织体系", "机构类型", "机构名称", "领导链接", "脚本序号"}
    if not required_rule_headers.issubset(rule_headers):
        raise ValueError(f"规则主表缺少字段：{sorted(required_rule_headers - set(rule_headers))}")
    if not ({"机构", "机构名称"} & set(rule_headers)):
        raise ValueError("规则主表缺少机构名称字段")
    if not ({"依据链接", "领导链接"} & set(rule_headers)):
        raise ValueError("规则主表缺少领导链接字段")
    if full_rows and not required_full_headers.issubset(full_rows[0]):
        raise ValueError(f"机构全量表缺少字段：{sorted(required_full_headers - set(full_rows[0]))}")

    full_records = [
        FullRecord(
            row["组织体系"], row["机构类型"], row["机构名称"], row["领导链接"], row["脚本序号"]
        )
        for row in full_rows
    ]
    indexes = build_indexes(full_records)
    audit_index = build_audit_index(audit_records, indexes["url"])
    manual_overrides = load_manual_overrides(mapping_report_path)
    matches: dict[str, MatchResult] = {}
    for rule in tqdm(rule_records, desc="匹配机构分类", unit="条"):
        sequence = rule["脚本序号"].zfill(4)
        matches[sequence] = (
            explicit_other_classification(rule)
            or manual_overrides.get(sequence)
            or match_rule(rule, indexes, audit_index, full_records)
        )

    sorted_rule_records, sorting_rows = sort_rules_by_full_table(
        rule_records, matches, full_records
    )
    sorting_headers = [
        "原位置", "新位置", "脚本序号", "机构名称", "组织体系", "机构类型",
        "机构全量表锚点行", "排序依据",
    ]
    write_tsv(sorting_report_path, sorting_headers, sorting_rows)

    mapping_headers = [
        "脚本序号", "规则主表机构名称", "机构全量表机构名称", "组织体系", "机构类型",
        "匹配方式", "复核状态", "置信度", "备注",
    ]
    mapping_rows: list[dict[str, str]] = []
    for rule in sorted_rule_records:
        sequence = rule["脚本序号"].zfill(4)
        match = matches[sequence]
        mapping_rows.append(
            {
                "脚本序号": sequence,
                "规则主表机构名称": rule_name(rule),
                "机构全量表机构名称": match.source_names,
                "组织体系": match.organization_system,
                "机构类型": match.institution_type,
                "匹配方式": match.method,
                "复核状态": match.review_status,
                "置信度": match.confidence,
                "备注": match.note,
            }
        )
    pending_rows = [row for row in mapping_rows if row["复核状态"] != "自动通过"]
    write_tsv(mapping_report_path, mapping_headers, mapping_rows)
    write_tsv(pending_report_path, mapping_headers, pending_rows)

    status_counts: dict[str, int] = defaultdict(int)
    method_counts: dict[str, int] = defaultdict(int)
    for row in mapping_rows:
        status_counts[row["复核状态"]] += 1
        method_counts[row["匹配方式"]] += 1
    logger.info("规则主表记录数：%d", len(rule_records))
    logger.info("机构全量表记录数：%d", len(full_records))
    logger.info("保留人工确认映射：%d 条", len(manual_overrides))
    logger.info("匹配状态：%s", dict(sorted(status_counts.items())))
    logger.info("匹配方式：%s", dict(sorted(method_counts.items())))
    logger.info("映射报告：%s", mapping_report_path)
    logger.info("待复核报告：%s", pending_report_path)
    logger.info("排序审计报告：%s", sorting_report_path)

    output_bytes = render_rule_table(rule_table_path, sorted_rule_records, matches)
    verify_rendered_rule_table(output_bytes, rule_records, rule_table_path)
    if not apply_changes:
        logger.info("当前为预览模式，未修改规则主表")
        return
    if output_bytes == rule_table_path.read_bytes():
        logger.info("规则主表分类已经是最新状态，无需重复备份或写回")
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"规则主表-字段与顺序调整前-{timestamp}.txt"
    shutil.copy2(rule_table_path, backup_path)
    temporary_path = rule_table_path.with_name(f".{rule_table_path.name}.{timestamp}.tmp")
    try:
        temporary_path.write_bytes(output_bytes)
        if temporary_path.read_bytes() != output_bytes:
            raise IOError("规则主表临时文件回读不一致")
        temporary_path.replace(rule_table_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    if rule_table_path.read_bytes() != output_bytes:
        raise IOError("规则主表正式写回后校验失败")
    logger.info("备份文件：%s", backup_path)
    logger.info("已经更新：%s", rule_table_path)


if __name__ == "__main__":
    input_rule_table_path = resolve_project_path(
        "important_people/workspace/source_data/规则主表.txt", anchor=__file__, must_exist=True
    )
    input_full_table_path = resolve_project_path(
        "important_people/workspace/source_data/机构主表.txt", anchor=__file__, must_exist=True
    )
    input_audit_path = resolve_project_path(
        "important_people/workspace/reports/机构目录/规则主表核对审计.txt",
        anchor=__file__,
        must_exist=True,
    )
    output_mapping_report_path = resolve_project_path(
        "important_people/workspace/source_data/机构分类映射表.txt", anchor=__file__
    )
    output_pending_report_path = resolve_project_path(
        "important_people/workspace/reports/机构分类待复核.txt", anchor=__file__
    )
    output_sorting_report_path = resolve_project_path(
        "important_people/workspace/reports/规则主表排序审计.txt", anchor=__file__
    )
    output_backup_dir = resolve_project_path(
        "important_people/workspace/source_data/backup", anchor=__file__
    )
    output_log_path = resolve_project_path(
        "important_people/workspace/log/同步机构分类到规则主表.log", anchor=__file__
    )
    should_apply_changes = True
    main(
        input_rule_table_path,
        input_full_table_path,
        input_audit_path,
        output_mapping_report_path,
        output_pending_report_path,
        output_sorting_report_path,
        output_backup_dir,
        output_log_path,
        should_apply_changes,
    )
