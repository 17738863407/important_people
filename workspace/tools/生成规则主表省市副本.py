"""根据机构名称推断规则主表的所属省市，并生成排序后的副本与审核报告。"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

try:
    from workspace.tools.project_paths import resolve_external_path, resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_external_path, resolve_project_path


EXPECTED_HEADER = [
    "组织体系", "目录链接", "机构类型", "机构层级", "所属省*", "所属市",
    "机构名称", "机构别称", "官网链接", "领导链接", "脚本序号", "备注",
]


def log_message(message: str, log_file: Path) -> None:
    """同时向控制台和日志文件输出信息。"""
    print(message)
    with log_file.open("a", encoding="utf-8") as file:
        file.write(f"{message}\n")


def calculate_sha256(file_path: Path) -> str:
    """计算文件的 SHA-256，验证原始主表未被改动。"""
    digest = hashlib.sha256()
    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_tsv(file_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """读取 UTF-8 制表符文本，并严格检查列数。"""
    lines = file_path.read_text(encoding="utf-8-sig").splitlines()
    if not lines:
        raise ValueError(f"文件为空：{file_path}")
    header = lines[0].split("\t")
    if header != EXPECTED_HEADER:
        raise ValueError(f"表头不符合预期：{header}")

    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        cells = line.split("\t")
        if len(cells) != len(header):
            raise ValueError(f"第 {line_number} 行列数异常：{len(cells)}")
        rows.append(dict(zip(header, cells, strict=True)))
    return header, rows


def write_tsv(file_path: Path, header: list[str], rows: Iterable[dict[str, str]]) -> None:
    """以 UTF-8 和制表符格式写入 TXT。"""
    output_lines = ["\t".join(header)]
    for row in rows:
        output_lines.append("\t".join(row.get(column, "") for column in header))
    file_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def load_administrative_data(json_path: Path) -> tuple[list[list[str | None]], list[list[str | None]]]:
    """读取从行政区划工作簿提取的结构化数据。"""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data["provinces"], data["details"]


def build_province_aliases(
    province_rows: list[list[str | None]],
    province_order: list[str],
) -> dict[str, str]:
    """建立省级行政区全称、标准简称与去后缀名称映射。"""
    aliases: dict[str, str] = {}
    for row in province_rows[1:]:
        for full_index, short_index in ((0, 1), (2, 3), (4, 5), (6, 7)):
            full_name = row[full_index] if len(row) > full_index else None
            short_name = row[short_index] if len(row) > short_index else None
            if not full_name:
                continue
            aliases[str(full_name)] = str(full_name)
            reduced = re.sub(r"(壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市)$", "", str(full_name))
            if len(reduced) >= 2:
                aliases[reduced] = str(full_name)
            if short_name:
                for item in str(short_name).split("/"):
                    if len(item) >= 2:
                        aliases[item] = str(full_name)

    # 参照表不含台湾省，排序与名称识别仍保留这一标准省级行政区。
    for province in province_order:
        aliases.setdefault(province, province)
        reduced = re.sub(r"(壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市)$", "", province)
        if len(reduced) >= 2:
            aliases.setdefault(reduced, province)
    return aliases


def build_place_index(
    detail_rows: list[list[str | None]],
) -> tuple[dict[str, set[tuple[str, str]]], dict[str, int]]:
    """建立地市、县区名称索引；同名异地的名称保留多项，供冲突检查使用。"""
    place_index: dict[str, set[tuple[str, str]]] = defaultdict(set)
    city_order: dict[str, int] = {}
    ignored_names = {"市辖区", "城区", "郊区", "新区", "矿区", "新城区", "城关区"}

    for row_number, row in enumerate(detail_rows[1:], start=1):
        if len(row) < 5:
            continue
        name, division_type, province, parent_city, alias = row[:5]
        if not name or not province or str(name) in ignored_names:
            continue
        name = str(name)
        division_type = str(division_type or "")
        province = str(province)
        parent_city = str(parent_city or "")

        if division_type in {"省会城市", "地级市", "自治州", "地区", "盟"}:
            city = name
            city_order.setdefault(f"{province}\t{city}", row_number)
        elif parent_city and parent_city != "省直辖":
            city = parent_city
        else:
            city = ""

        candidate_names = {name}
        if alias:
            candidate_names.update(item.strip() for item in str(alias).split("/") if item.strip())

        if division_type in {"省会城市", "地级市", "县级市"} and name.endswith("市"):
            reduced = name[:-1]
            if len(reduced) >= 2:
                candidate_names.add(reduced)
        elif division_type == "自治州" and name.endswith("自治州"):
            reduced = name.removesuffix("自治州")
            if len(reduced) >= 2:
                candidate_names.add(reduced + "州")
        elif division_type == "地区" and name.endswith("地区"):
            reduced = name.removesuffix("地区")
            if len(reduced) >= 2:
                candidate_names.add(reduced)

        for candidate in candidate_names:
            if len(candidate) >= 2 and candidate not in ignored_names:
                place_index[candidate].add((province, city))

    return place_index, city_order


def normalize_org_for_prefix(org: str) -> str:
    """移除常见政治机构前缀，便于识别紧随其后的行政区名称。"""
    prefixes = (
        "中国共产党",
        "中共",
        "中国人民政治协商会议",
        "政协",
    )
    normalized = org.strip()
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    return normalized


def is_provincial_four_body(org: str, province_order: list[str]) -> bool:
    """判断是否为省级党委、人大、政府、政协四套机构本体。"""
    for province in province_order:
        short = re.sub(r"(壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市)$", "", province)
        patterns = {
            f"{short}省委",
            f"{short}市委",
            f"中共{short}省委",
            f"{province}党委",
            f"中共{province}委员会",
            f"中国共产党{province}委员会",
            f"{province}人民代表大会",
            f"{province}人民代表大会常务委员会",
            f"{province}人大常委会",
            f"{province}人民政府",
            f"中国人民政治协商会议{province}委员会",
            f"政协{province}委员会",
            f"{province}政协",
        }
        if org in patterns:
            return True
    return False


def find_explicit_location(
    org: str,
    province_aliases: dict[str, str],
    place_index: dict[str, set[tuple[str, str]]],
) -> tuple[str, str, str] | None:
    """从机构名中识别明确地域；发生同名异地或多地冲突时不作推断。"""
    normalized = normalize_org_for_prefix(org)
    candidates: set[tuple[str, str, str]] = set()

    full_province_matches = {
        province
        for alias, province in province_aliases.items()
        if alias == province and alias in org
    }
    if len(full_province_matches) > 1:
        return None
    explicit_province = next(iter(full_province_matches), "")

    # 完整行政区名称可出现在机构名中；去“市”的简称仅接受机构名开头，降低误判。
    for place_name, locations in place_index.items():
        is_full_name = place_name.endswith(("市", "州", "地区", "盟", "县", "区", "旗"))
        if explicit_province and not is_full_name:
            continue
        matched = place_name in org if is_full_name else normalized.startswith(place_name)
        if not matched:
            continue
        for province, city in locations:
            if explicit_province and province != explicit_province:
                continue
            candidates.add((province, city, place_name))

    # 优先采用更长、更明确的行政区名称；同长度若指向不同地区则判定为冲突。
    if candidates:
        max_length = max(len(item[2]) for item in candidates)
        strongest = {item for item in candidates if len(item[2]) == max_length}
        locations = {(item[0], item[1]) for item in strongest}
        if len(locations) == 1:
            province, city = next(iter(locations))
            names = "、".join(sorted({item[2] for item in strongest}))
            if province in {"北京市", "天津市", "上海市", "重庆市"}:
                city = ""
            return province, city, f"机构名命中行政区：{names}"
        return None

    if explicit_province:
        return explicit_province, "", f"机构名命中省级行政区：{explicit_province}"

    # 省级全称或不少于两字的去后缀名称可出现在机构名中；单字简称未进入索引。
    province_matches: list[tuple[str, str]] = []
    for alias, province in province_aliases.items():
        if alias in org:
            province_matches.append((alias, province))
    if province_matches:
        max_length = max(len(item[0]) for item in province_matches)
        strongest = {(alias, province) for alias, province in province_matches if len(alias) == max_length}
        provinces = {province for _, province in strongest}
        if len(provinces) == 1:
            province = next(iter(provinces))
            alias = sorted(alias for alias, _ in strongest)[0]
            return province, "", f"机构名命中省级行政区：{alias}"
    return None


def is_obvious_national_org(
    org: str,
    ministry_prefixes: tuple[str, ...],
    known_national_names: set[str],
    national_name_exceptions: set[str],
) -> bool:
    """保守识别机构名明确显示为全国或中央层级的记录。"""
    national_prefixes = (
        "中共中央",
        "中央",
        "国务院",
        "全国",
        "中华全国",
        "国家",
        "最高人民法院",
        "最高人民检察院",
        "中国人民解放军",
        "中国人民政治协商会议全国委员会",
    )
    if org in known_national_names:
        return True
    if org.startswith(national_prefixes) or org.startswith(ministry_prefixes):
        return True

    # “中国”“中华”冠名且名称中没有明确属地的机构通常为全国层级；少数历史冠名例外单列。
    if org.startswith(("中国", "中华")) and org not in national_name_exceptions:
        return True

    regional_central_patterns = (
        r"^(华东|东北|华北|西北|西南|华南)核与辐射安全监督站$",
        r"^(长江|海河|淮河|黄河|珠江|松辽).*(委员会|监督管理局|航务管理局)$",
    )
    if any(re.search(pattern, org) for pattern in regional_central_patterns):
        return True

    national_china_keywords = (
        "科学院",
        "社会科学院",
        "工程院",
        "协会",
        "学会",
        "联合会",
        "总工会",
        "总会",
        "委员会",
        "总局",
        "总署",
    )
    return org.startswith("中国") and any(keyword in org for keyword in national_china_keywords)


def infer_location(
    org: str,
    province_order: list[str],
    province_aliases: dict[str, str],
    place_index: dict[str, set[tuple[str, str]]],
    central_soe_names: set[str],
    known_university_locations: dict[str, tuple[str, str]],
    ministry_prefixes: tuple[str, ...],
    known_national_names: set[str],
    national_name_exceptions: set[str],
    named_place_institutions: dict[str, tuple[str, str]],
) -> tuple[str, str, str, str]:
    """按用户规则返回省、市、推断规则和审核说明。"""
    if org == "中央人民政府驻香港特别行政区联络办公室":
        return "全国", "", "指定全国机构", "用户明确指定"

    if org in central_soe_names:
        return "全国", "", "中央级国企", "按已核对的中央企业名称识别"

    if is_provincial_four_body(org, province_order):
        return "全国", "", "省级四套机构", "省级党委、人大、政府、政协按全国归属"

    # 已人工核对的全国机构优先于名称中的服务对象或驻在地，例如驻澳门联络机构、国务院台办。
    if org in known_national_names:
        return "全国", "", "明显全国机构", "机构本体为中央或全国层级"

    explicit = find_explicit_location(org, province_aliases, place_index)
    if explicit:
        province, city, evidence = explicit
        if "大学" in org or (org.endswith("学院") and "科学院" not in org):
            return province, city, "高校属地", evidence
        if any(keyword in org for keyword in ("医院", "医疗中心", "卫生院")):
            return province, city, "医院属地", evidence
        return province, city, "机构名称属地", evidence

    if org in known_university_locations:
        province, city = known_university_locations[org]
        return province, city, "高校属地", "高校校址人工核对表"

    if org in named_place_institutions:
        province, city = named_place_institutions[org]
        return province, city, "专名属地", "机构专名可唯一回指行政区"

    if is_obvious_national_org(org, ministry_prefixes, known_national_names, national_name_exceptions):
        return "全国", "", "明显全国机构", "机构名称含明确中央、国家或全国层级标识"

    category = "普通待审核"
    if "大学" in org or (org.endswith("学院") and "科学院" not in org):
        category = "高校待审核"
    elif any(keyword in org for keyword in ("医院", "医疗中心", "卫生院")):
        category = "医院待审核"
    elif any(keyword in org for keyword in ("集团有限公司", "有限责任公司", "股份有限公司", "总公司")):
        category = "企业待审核"
    return "", "", category, "机构名称不足以可靠确定地域，保持空白"


def build_report(
    report_path: Path,
    source_path: Path,
    output_path: Path,
    source_hash: str,
    result_rows: list[dict[str, str]],
    audit_rows: list[dict[str, str | int]],
    rule_counts: Counter[str],
) -> None:
    """生成包含汇总、未确定地域清单和全量推断轨迹的审核报告。"""
    unresolved = [row for row in audit_rows if not row["所属省*"]]
    province_counts = Counter(row["所属省*"] or "未确定" for row in result_rows)
    lines = [
        "规则主表省市推断审核报告",
        f"生成时间\t{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"原始文件\t{source_path}",
        f"输出副本\t{output_path}",
        f"原始文件SHA256\t{source_hash}",
        f"业务记录数\t{len(result_rows)}",
        f"已确定地域\t{len(result_rows) - len(unresolved)}",
        f"未确定地域\t{len(unresolved)}",
        "",
        "推断规则统计",
        "推断规则\t数量",
    ]
    lines.extend(f"{rule}\t{count}" for rule, count in rule_counts.most_common())
    lines.extend(["", "归属统计", "所属省*\t数量"])
    lines.extend(f"{province}\t{count}" for province, count in province_counts.most_common())
    lines.extend(
        [
            "",
            "未确定地域清单（需用户审核）",
            "原始次序\t脚本序号\t机构\t类别\t说明",
        ]
    )
    for row in unresolved:
        lines.append(
            f"{row['原始次序']}\t{row['脚本序号']}\t{row['机构']}\t{row['推断规则']}\t{row['审核说明']}"
        )
    lines.extend(
        [
            "",
            "全量推断轨迹",
            "原始次序\t排序后次序\t脚本序号\t机构\t所属省*\t所属市\t推断规则\t审核说明",
        ]
    )
    for row in audit_rows:
        lines.append(
            "\t".join(
                str(row[column])
                for column in (
                    "原始次序",
                    "排序后次序",
                    "脚本序号",
                    "机构",
                    "所属省*",
                    "所属市",
                    "推断规则",
                    "审核说明",
                )
            )
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_results(
    source_rows: list[dict[str, str]],
    result_rows: list[dict[str, str]],
    province_order: list[str],
    central_soe_names: set[str],
) -> None:
    """验证记录完整性、非地域字段、全国城市空值和重点业务规则。"""
    if len(source_rows) != len(result_rows):
        raise ValueError("输出记录数与原始记录数不一致")
    source_by_id = {row["脚本序号"]: row for row in source_rows}
    result_by_id = {row["脚本序号"]: row for row in result_rows}
    if len(source_by_id) != len(source_rows) or set(source_by_id) != set(result_by_id):
        raise ValueError("脚本序号存在重复、缺失或新增")

    non_location_columns = [
        "组织体系", "目录链接", "机构类型", "机构层级", "机构名称",
        "机构别称", "官网链接", "领导链接", "脚本序号", "备注"
    ]
    for rule_id, source_row in source_by_id.items():
        result_row = result_by_id[rule_id]
        for column in non_location_columns:
            if source_row[column] != result_row[column]:
                raise ValueError(f"非地域字段被改动：{rule_id} {column}")

    allowed_provinces = set(province_order) | {"全国", ""}
    for row in result_rows:
        if row["所属省*"] not in allowed_provinces:
            raise ValueError(f"省级行政区不在允许范围：{row}")
        if row["所属省*"] == "全国" and row["所属市"]:
            raise ValueError(f"全国机构不应填写所属市：{row}")
        if row["所属市"] == "省直辖":
            raise ValueError(f"所属市不得使用行政区划表内部标记“省直辖”：{row}")
        if is_provincial_four_body(row["机构名称"], province_order) and row["所属省*"] != "全国":
            raise ValueError(f"省级四套机构未归属全国：{row['机构名称']}")

    exact_special = next(
        (row for row in result_rows if row["机构名称"] == "中央人民政府驻香港特别行政区联络办公室"),
        None,
    )
    if exact_special and exact_special["所属省*"] != "全国":
        raise ValueError("中央人民政府驻香港特别行政区联络办公室未归属全国")

    for row in result_rows:
        if row["机构名称"] in central_soe_names and row["所属省*"] != "全国":
            raise ValueError(f"中央级国企未归属全国：{row['机构名称']}")


def main(
    source_path: Path,
    admin_json_path: Path,
    output_path: Path,
    report_path: Path,
    log_dir: Path,
    province_order: list[str],
    central_soe_names: set[str],
    known_university_locations: dict[str, tuple[str, str]],
    ministry_prefixes: tuple[str, ...],
    known_national_names: set[str],
    national_name_exceptions: set[str],
    named_place_institutions: dict[str, tuple[str, str]],
) -> None:
    """执行读取、推断、排序、输出、报告和完整性核验。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"规则主表省市推断_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    source_hash_before = calculate_sha256(source_path)
    header, source_rows = read_tsv(source_path)
    province_rows, detail_rows = load_administrative_data(admin_json_path)
    province_aliases = build_province_aliases(province_rows, province_order)
    place_index, city_order = build_place_index(detail_rows)
    log_message(f"读取规则主表：{len(source_rows)} 条", log_file)
    log_message(f"行政区划名称索引：{len(place_index)} 个", log_file)

    result_rows: list[dict[str, str]] = []
    audit_rows: list[dict[str, str | int]] = []
    rule_counts: Counter[str] = Counter()
    for original_index, source_row in enumerate(tqdm(source_rows, desc="推断省市", unit="条"), start=1):
        result_row = source_row.copy()
        if source_row["所属省*"] or source_row["所属市"]:
            province = source_row["所属省*"]
            city = source_row["所属市"]
            rule = "保留原值"
            note = "原始主表已有地域值"
        else:
            province, city, rule, note = infer_location(
                source_row["机构名称"],
                province_order,
                province_aliases,
                place_index,
                central_soe_names,
                known_university_locations,
                ministry_prefixes,
                known_national_names,
                national_name_exceptions,
                named_place_institutions,
            )
        result_row["所属省*"] = province
        result_row["所属市"] = city
        result_rows.append(result_row)
        audit_rows.append(
            {
                "原始次序": original_index,
                "排序后次序": 0,
                "脚本序号": source_row["脚本序号"],
                "机构": source_row["机构名称"],
                "所属省*": province,
                "所属市": city,
                "推断规则": rule,
                "审核说明": note,
            }
        )
        rule_counts[rule] += 1

    province_rank = {province: index for index, province in enumerate(["全国", *province_order])}
    original_rank = {row["脚本序号"]: index for index, row in enumerate(source_rows)}

    def sort_key(row: dict[str, str]) -> tuple[int, int, int]:
        province = row["所属省*"]
        city = row["所属市"]
        province_value = province_rank.get(province, 999)
        city_value = 0 if not city else city_order.get(f"{province}\t{city}", 999_998)
        return province_value, city_value, original_rank[row["脚本序号"]]

    result_rows.sort(key=sort_key)
    if result_rows != sorted(result_rows, key=sort_key):
        raise ValueError("输出结果未按归属稳定排序")
    sorted_rank = {row["脚本序号"]: index for index, row in enumerate(result_rows, start=1)}
    for row in audit_rows:
        row["排序后次序"] = sorted_rank[str(row["脚本序号"])]
    audit_rows.sort(key=lambda row: int(row["排序后次序"]))

    validate_results(source_rows, result_rows, province_order, central_soe_names)
    write_tsv(output_path, header, result_rows)
    build_report(report_path, source_path, output_path, source_hash_before, result_rows, audit_rows, rule_counts)

    source_hash_after = calculate_sha256(source_path)
    if source_hash_before != source_hash_after:
        raise RuntimeError("原始规则主表哈希发生变化，已停止交付")
    log_message(f"已生成副本：{output_path}", log_file)
    log_message(f"已生成审核报告：{report_path}", log_file)
    log_message(f"原始文件哈希未变：{source_hash_after}", log_file)
    log_message(f"已确定地域：{sum(1 for row in result_rows if row['所属省*'])} 条", log_file)
    log_message(f"未确定地域：{sum(1 for row in result_rows if not row['所属省*'])} 条", log_file)


if __name__ == "__main__":
    source_file = resolve_project_path(
        "important_people/workspace/source_data/规则主表.txt", anchor=__file__, must_exist=True
    )
    admin_json_file = resolve_external_path("IMPORTANT_PERSON_ADMIN_DIVISIONS_JSON")
    output_file = resolve_project_path(
        "important_people/规则主表-省市推断副本.txt", anchor=__file__
    )
    report_file = resolve_project_path(
        "important_people/workspace/reports/规则主表省市推断审核报告.txt", anchor=__file__
    )
    log_folder = resolve_project_path("important_people/workspace/log", anchor=__file__)
    standard_province_order = [
        "北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省", "吉林省", "黑龙江省",
        "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省", "河南省",
        "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省", "重庆市", "四川省", "贵州省",
        "云南省", "西藏自治区", "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区",
        "香港特别行政区", "澳门特别行政区", "台湾省",
    ]
    central_enterprises = {
        "中国邮政集团有限公司办公厅", "中国建筑股份有限公司", "国家融资担保基金有限责任公司", "中粮集团",
        "中国东方演艺集团有限公司", "中国动漫集团有限公司", "中国数字文化集团有限公司",
        "中国文化传媒集团有限公司", "国家珠宝玉石首饰检验集团有限公司",
        "中国水利水电出版传媒集团有限公司", "中国航空发动机集团有限公司",
        "中国航空工业集团有限公司", "矿冶科技集团有限公司", "中国机械科学研究总院集团有限公司",
        "中国航空器材集团有限公司", "中国航天科工集团有限公司", "中国煤炭地质总局",
        "中国诚通控股集团有限公司", "中国节能环保集团有限公司", "中国电气装备集团有限公司",
        "国家能源投资集团有限责任公司", "中国电子科技集团有限公司", "中国广核集团有限公司",
        "中国华电集团有限公司", "中国大唐集团有限公司", "华侨城集团有限公司", "中国盐业集团有限公司",
        "中国华能集团有限公司", "中国国际技术智力合作集团有限公司", "中国钢研科技集团有限公司",
        "中国建材集团有限公司", "中国有色矿业集团有限公司", "中国商用飞机有限责任公司",
        "华润（集团）有限公司", "中国铁路工程集团有限公司", "中国国新控股有限责任公司",
        "中国中车集团有限公司", "中国资源循环集团有限公司", "中国铁路通信信号集团有限公司",
        "中国建筑集团有限公司", "中国船舶集团有限公司", "中国南水北调集团有限公司",
        "中国长江三峡集团有限公司", "东风汽车集团有限公司", "中国东方电气集团有限公司",
        "中国第一汽车集团有限公司", "中国有研科技集团有限公司", "中国通用技术（集团）控股有限责任公司",
        "哈尔滨电气集团有限公司", "中国五矿集团有限公司", "中国兵器工业集团有限公司",
        "国家石油天然气管网集团有限公司", "中国保利集团有限公司", "国家开发投资集团有限公司",
        "国家电网有限公司", "中国中化控股有限责任公司", "中国机械工业集团有限公司",
        "中国石油化工集团有限公司", "中国医药集团有限公司", "国家电力投资集团有限公司",
        "中国民航信息集团有限公司", "新兴际华集团有限公司", "中国航空集团有限公司",
        "鞍钢集团有限公司", "中国宝武钢铁集团有限公司", "中国检验认证（集团）有限公司",
        "中国建设科技有限公司", "中国煤炭科工集团有限公司", "中国东方航空集团有限公司",
        "中国电子信息产业集团有限公司", "中国能源建设集团有限公司", "中国林业集团有限公司",
        "中国一重集团有限公司", "中国安能建设集团有限公司", "中国中煤能源集团有限公司",
        "中国黄金集团有限公司", "中国电信集团有限公司", "中国信息通信科技集团有限公司",
        "中国国际工程咨询有限公司", "中国冶金地质总局", "招商局集团有限公司",
        "中国农业发展集团有限公司", "中国化学工程集团有限公司", "中国核工业集团有限公司",
        "中国海洋石油集团有限公司", "中国石油天然气集团有限公司", "中国远洋海运集团有限公司",
        "中国融通资产管理集团有限公司", "中国南方航空集团有限公司", "中国南方电网有限责任公司",
        "中国兵器装备集团有限公司", "中国旅游集团有限公司[香港中旅（集团）有限公司]",
        "中国电力建设集团有限公司", "中国稀土集团有限公司", "中国航天科技集团有限公司",
    }
    university_locations = {
        "北京航空航天大学": ("北京市", ""), "中央司法警官学院": ("河北省", "保定市"),
        "国家法官学院": ("北京市", ""), "大连海事大学": ("辽宁省", "大连市"),
        "哈尔滨工业大学": ("黑龙江省", "哈尔滨市"), "哈尔滨工程大学": ("黑龙江省", "哈尔滨市"),
        "中央民族大学": ("北京市", ""), "大连民族大学": ("辽宁省", "大连市"),
        "南京理工大学": ("江苏省", "南京市"), "北方民族大学": ("宁夏回族自治区", "银川市"),
        "南京航空航天大学": ("江苏省", "南京市"), "西北工业大学": ("陕西省", "西安市"),
        "国家开放大学": ("北京市", ""), "北京大学": ("北京市", ""),
        "中南民族大学": ("湖北省", "武汉市"), "西南民族大学": ("四川省", "成都市"),
        "清华大学": ("北京市", ""), "西北民族大学": ("甘肃省", "兰州市"),
        "华中科技大学": ("湖北省", "武汉市"),
    }
    central_ministry_prefixes = (
        "外交部", "国防部", "教育部", "科学技术部", "工业和信息化部", "公安部", "民政部",
        "司法部", "财政部", "人力资源和社会保障部", "自然资源部", "生态环境部",
        "住房和城乡建设部", "交通运输部", "水利部", "农业农村部", "商务部", "文化和旅游部",
        "退役军人事务部", "应急管理部", "中国人民银行", "审计署",
    )
    obvious_national_names = {
        "九三学社", "海关总署", "中华人民共和国国务院", "共青团中央", "新华通讯社",
        "中央人民政府驻澳门特别行政区联络办公室", "国务院台湾事务办公室（中央台湾工作办公室）",
        "中华全国台湾同胞联谊会", "中日友好环境保护中心（生态环境部环境发展中心）",
        "全国人大常委会香港特别行政区基本法委员会", "全国人大常委会澳门特别行政区基本法委员会",
        "台湾民主自治同盟", "台湾少数民族研究会",
        "黄埔军校同学会", "《中国旅游报》社有限公司", "中外文化和旅游交流中心",
        "太湖流域东海海域生态环境监督管理局",
        "人民法院出版社有限公司", "人民法院新闻传媒总社", "人民法院信息技术服务中心",
        "高等教育出版社", "人民教育出版社", "法律出版社", "故宫博物院", "梅兰芳纪念馆",
        "民族文化宫", "民族画报社", "民族出版社", "科技日报社", "欧美同学会",
        "联合国教科文组织全国委员会秘书处", "全面依法治国研究中心", "司法鉴定科学研究院",
        "语言文字应用研究所", "课程教材研究所", "土壤与农业农村生态环境监管技术中心",
        "语文出版社",
    }
    national_prefix_exceptions = {"中国测试技术研究院"}
    geographic_name_locations = {
        "大熊猫国家公园甘肃管理局": ("甘肃省", ""),
        "三江源国家公园管理局": ("青海省", ""),
        "神农架国家公园管理局": ("湖北省", ""),
    }
    main(
        source_file,
        admin_json_file,
        output_file,
        report_file,
        log_folder,
        standard_province_order,
        central_enterprises,
        university_locations,
        central_ministry_prefixes,
        obvious_national_names,
        national_prefix_exceptions,
        geographic_name_locations,
    )
