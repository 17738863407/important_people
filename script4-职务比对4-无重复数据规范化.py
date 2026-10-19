# -*- coding: utf-8 -*-
"""关联无重复在线比对数据与重要人物规范化表，生成最终 xlsx。

    关联规则：
    以「姓名、本地职务、依据链接」对应规范化表的「姓名*、职务*、依据链接」进行关联，
    字段为：
        姓名*	职务*	老数据职务	排序*	职级*	所属省*	所属市	依据链接	依据说明	维护人	机构

    「排序*」和「职级*」分别继承上一步文件的「排序」和「职级」，其他规范化
    字段从重要人物规范化表关联取得。

    筛选排序规则：
    1. 比较第2列「职务*」与第3列「老数据职务」的数据元素（按中文逗号「，」、
       中文顿号「、」拆分，老数据职务另按「/」拆分，因为多条之间用「/」连接）；
       只有完全相同的元素才算重复，没有任何重复的行才导出。
    2. 按提醒类型排序（来源为更新提醒表的第4列）：「需要新增」在前，「职务变更」在后；
       同类型内再按「机构」类别排序：
       党中央机构、国务院机构、全国政协、民主党派、
       31个省级行政区的政府、党委、人大、政协、厅级部门，其余归入「其他」放在最后。

生成的 xlsx 带表头冻结、自动筛选与自动换行。

固定输入：项目根目录下的「职务比对3：无重复数据.txt」和
「职务规范4：扩充.txt」。
固定输出：项目根目录下的「职务比对4：无重复数据规范化.xlsx」。
"""

from __future__ import annotations

import difflib
import logging
import re
import sys
from pathlib import Path

from crawler_core.paths import resolve_path_argument, timestamped_output_path


SPLIT_PATTERN = re.compile(r"[，、/]")

TYPE_ORDER = {"需要新增": 0, "职务变更": 1}

CATEGORY_ORDER = [
    "党中央机构",
    "国务院机构",
    "全国政协",
    "民主党派",
    "省级政府",
    "省级党委",
    "省级人大",
    "省级政协",
    "省级厅级部门",
    "其他",
]

# 国务院组成部门、直属机构、直属事业单位等中央机构关键词（按机构名开头匹配）
CENTRAL_KEYWORDS = [
    "国务院办公厅",
    "国务院国有资产监督管理委员会",
    "国务院研究室",
    "国务院港澳事务办公室",
    "国务院台湾事务办公室",
    "外交部",
    "国防部",
    "国家发展和改革委员会",
    "教育部",
    "科学技术部",
    "工业和信息化部",
    "国家民族事务委员会",
    "公安部",
    "国家安全部",
    "民政部",
    "司法部",
    "财政部",
    "人力资源和社会保障部",
    "自然资源部",
    "生态环境部",
    "住房和城乡建设部",
    "交通运输部",
    "水利部",
    "农业农村部",
    "商务部",
    "文化和旅游部",
    "国家卫生健康委员会",
    "退役军人事务部",
    "应急管理部",
    "中国人民银行",
    "审计署",
    "海关总署",
    "国家税务总局",
    "国家市场监督管理总局",
    "国家广播电视总局",
    "国家体育总局",
    "国家统计局",
    "国家国际发展合作署",
    "国家医疗保障局",
    "国家机关事务管理局",
    "国家能源局",
    "国家国防科技工业局",
    "国家烟草专卖局",
    "国家移民管理局",
    "国家林业和草原局",
    "国家铁路局",
    "中国民用航空局",
    "国家邮政局",
    "国家文物局",
    "国家中医药管理局",
    "国家矿山安全监察局",
    "国家外汇管理局",
    "国家药品监督管理局",
    "国家知识产权局",
    "国家互联网信息办公室",
    "国家乡村振兴局",
    "国家粮食和物资储备局",
    "国家疾病预防控制局",
    "国家信访局",
    "国家航天局",
    "国家原子能机构",
    "国家自然科学基金委员会",
    "全国社会保障基金理事会",
    "中国证券监督管理委员会",
    "国家金融监督管理总局",
    "中国科学院",
    "中国工程院",
    "中国社会科学院",
    "中国气象局",
    "新华通讯社",
    "水利委员会",
]

DEMOCRATIC_PARTY_KEYWORDS = [
    "中国国民党革命委员会",
    "中国民主同盟",
    "中国民主建国会",
    "中国民主促进会",
    "中国农工民主党",
    "中国致公党",
    "九三学社",
    "台湾民主自治同盟",
    "民革",
    "民盟",
    "民建",
    "民进",
    "农工党",
    "致公党",
    "台盟",
]

# 31 个省级行政区名称（用于识别省级厅级部门）
PROVINCE_KEYWORDS = [
    "北京",
    "天津",
    "河北",
    "山西",
    "内蒙古",
    "辽宁",
    "吉林",
    "黑龙江",
    "上海",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "广西",
    "海南",
    "重庆",
    "四川",
    "贵州",
    "云南",
    "西藏",
    "陕西",
    "甘肃",
    "青海",
    "宁夏",
    "新疆",
]


def setup_logging(log_path: Path) -> None:
    """配置日志：同时输出到控制台与日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def clean_cell(value: object) -> str:
    """清理单元格中的制表符与换行，避免破坏 TSV 结构。"""
    if value is None:
        return ""
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def split_elements(text: str) -> list[str]:
    """把职务文本拆成数据元素（中文逗号、中文顿号，老数据职务另含「/」）。"""
    return [part.strip() for part in SPLIT_PATTERN.split(text) if part.strip()]


def read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    """读取 TSV：返回表头与各行单元格列表。"""
    with open(path, encoding="utf-8") as fh:
        lines = [line.rstrip("\n") for line in fh if line.strip()]
    if not lines:
        raise ValueError(f"文件为空：{path}")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    return header, rows


def classify_org(org: str) -> str:
    """把机构归类到排序类别中，无法归类的放入「其他」。"""
    org = org.strip()
    if not org:
        return "其他"
    if "—" in org and ("市委书记" in org or "各地级市" in org):
        # 组合标签（如 金华市—市委书记、市长、政协主席、人大常委会主任）
        return "其他"
    if any(kw in org for kw in DEMOCRATIC_PARTY_KEYWORDS):
        return "民主党派"
    if org.startswith("全国政协") or "中国人民政治协商会议" in org:
        return "全国政协"
    if org.startswith("中央"):
        return "党中央机构"
    for kw in CENTRAL_KEYWORDS:
        if kw in org:
            return "国务院机构"
    if "全国人大" in org:  # 全国人大及其常委会不在需求分类中，归入其他
        return "其他"
    if any(kw in org for kw in ["省委", "市委", "自治区党委", "地委", "州委"]):
        return "省级党委"
    if "人大常委会" in org or org.endswith("人大"):
        return "省级人大"
    if "政协" in org:
        return "省级政协"
    if "人民政府" in org or "政府" in org:
        return "省级政府"
    local_keywords = PROVINCE_KEYWORDS + ["海口", "兰州", "市", "省", "自治区", "自治州", "地区"]
    if any(kw in org for kw in local_keywords):
        return "省级厅级部门"
    return "其他"


def build_indexes(normalized_rows: list[list[str]], ni: dict[str, int]) -> tuple[dict, dict]:
    """构建规范化表索引：精确键与（姓名*，依据链接）键。"""
    exact_index: dict[tuple[str, str, str], list[list[str]]] = {}
    name_link_index: dict[tuple[str, str], list[list[str]]] = {}
    for row in normalized_rows:
        name = row[ni["姓名*"]]
        duty = row[ni["职务*"]]
        link = row[ni["依据链接"]]
        exact_index.setdefault((name, duty, link), []).append(row)
        name_link_index.setdefault((name, link), []).append(row)
    return exact_index, name_link_index


def duty_domain_score(duty: str, candidate_duty: str) -> int:
    """按职务关键词给候选行打分，用于多候选时消歧。"""
    score = 0
    if "党委" in duty or "书记" in duty:
        score += 2 if ("党委" in candidate_duty or "书记" in candidate_duty) else -2
    if "人大" in duty or "常委会" in duty:
        score += 2 if "人大" in candidate_duty else -2
    if "政协" in duty:
        score += 2 if "政协" in candidate_duty else -2
    if "政府" in duty or "市长" in duty or "省长" in duty or "主席" in duty:
        score += 2 if ("政府" in candidate_duty or "市长" in candidate_duty or "省长" in candidate_duty) else -2
    return score


def join_reminder_row(
    row: list[str],
    ri: dict[str, int],
    exact_index: dict,
    name_link_index: dict,
    ni: dict[str, int],
) -> tuple[list[str] | None, str]:
    """关联一条更新提醒到规范化表，返回（规范化行，关联方式）。"""
    name = row[ri["姓名"]]
    duty = row[ri["本地职务"]]
    link = row[ri["依据链接"]]

    # 1. 精确匹配（姓名*、职务*、依据链接）
    exact_hits = exact_index.get((name, duty, link), [])
    if exact_hits:
        return exact_hits[0], "exact"

    candidates = name_link_index.get((name, link), [])
    duty_elems = set(split_elements(duty))

    # 2. 职务元素完全包含（姓名+链接 且 本地职务元素 ⊆ 职务* 元素）
    element_hits = [
        c for c in candidates if duty_elems and duty_elems <= set(split_elements(c[ni["职务*"]]))
    ]
    if len(element_hits) == 1:
        return element_hits[0], "element"
    if len(element_hits) > 1:
        best = max(element_hits, key=lambda c: duty_domain_score(duty, c[ni["职务*"]]))
        return best, "element_multi"

    # 3. 姓名+链接唯一候选（容忍“省省/市市”等文本噪声）
    if len(candidates) == 1:
        return candidates[0], "name_link"

    # 4. 姓名+链接多候选：按元素重合度与职务关键词打分
    if candidates:
        def score(c: list[str]) -> float:
            cand_elems = set(split_elements(c[ni["职务*"]]))
            common = len(duty_elems & cand_elems)
            ratio = difflib.SequenceMatcher(None, duty, c[ni["职务*"]]).ratio()
            return common * 1000 + ratio + duty_domain_score(duty, c[ni["职务*"]])

        best = max(candidates, key=score)
        return best, "scored"

    return None, "none"


def build_linked_rows(
    reminder_rows: list[list[str]],
    ri: dict[str, int],
    normalized_rows: list[list[str]],
    ni: dict[str, int],
) -> tuple[list[dict[str, str]], list[str], dict[str, int]]:
    """关联并构造 11 列输出行，返回（输出行列表、未匹配姓名、关联方式统计）。"""
    exact_index, name_link_index = build_indexes(normalized_rows, ni)
    out_rows: list[dict[str, str]] = []
    unmatched: list[str] = []
    mode_counts: dict[str, int] = {}

    for row in reminder_rows:
        nrow, mode = join_reminder_row(row, ri, exact_index, name_link_index, ni)
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        if nrow is not None:
            linked = {
                "姓名*": nrow[ni["姓名*"]],
                "职务*": nrow[ni["职务*"]],
                "老数据职务": row[ri["老数据职务"]],
                "排序*": row[ri["排序"]],
                "职级*": row[ri["职级"]],
                "所属省*": nrow[ni["所属省*"]],
                "所属市": nrow[ni["所属市"]],
                "依据链接": nrow[ni["依据链接"]],
                "依据说明": nrow[ni["依据说明"]],
                "维护人": nrow[ni["维护人"]],
                "机构": nrow[ni["机构"]],
                "_提醒类型": row[ri["提醒类型"]],
            }
        else:
            unmatched.append(row[ri["姓名"]])
            linked = {
                "姓名*": row[ri["姓名"]],
                "职务*": row[ri["本地职务"]],
                "老数据职务": row[ri["老数据职务"]],
                "排序*": row[ri["排序"]],
                "职级*": row[ri["职级"]],
                "所属省*": "",
                "所属市": "",
                "依据链接": row[ri["依据链接"]],
                "依据说明": "",
                "维护人": "",
                "机构": "",
                "_提醒类型": row[ri["提醒类型"]],
            }
        out_rows.append(linked)
    return out_rows, unmatched, mode_counts


def has_overlap(duty: str, remote_duties: str) -> bool:
    """判断职务*与老数据职务是否存在完全相同的元素。"""
    duty_elems = set(split_elements(duty))
    remote_elems = set(split_elements(remote_duties))
    return bool(duty_elems & remote_elems)


def prepare_filtered_rows(out_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """筛选出无重复元素的行，并按提醒类型、机构类别排序。"""
    kept = [row for row in out_rows if not has_overlap(row["职务*"], row["老数据职务"])]

    def org_category(row: dict[str, str]) -> int:
        category = classify_org(row["机构"])
        if category in CATEGORY_ORDER:
            return CATEGORY_ORDER.index(category)
        return len(CATEGORY_ORDER)

    kept.sort(
        key=lambda r: (TYPE_ORDER.get(r["_提醒类型"], 99), org_category(r))
    )
    return kept


def write_xlsx(rows: list[dict[str, str]], output_path: Path, sheet_title: str) -> None:
    """写出与 txt 内容一致的 xlsx：表头加粗、冻结首行、自动筛选、自动换行。"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except Exception as error:
        raise RuntimeError("缺少 openpyxl，无法生成 xlsx") from error

    columns = [
        "姓名*",
        "职务*",
        "老数据职务",
        "排序*",
        "职级*",
        "所属省*",
        "所属市",
        "依据链接",
        "依据说明",
        "维护人",
        "机构",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    ws = workbook.active
    ws.title = sheet_title

    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="FFD9E1F2", end_color="FFD9E1F2", fill_type="solid")
    wrap_alignment = Alignment(wrap_text=True, vertical="top")

    ws.append(columns)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")

    for row in rows:
        ws.append([clean_cell(row[col]) for col in columns])

    # 依据链接设置为可点击超链接
    link_col = columns.index("依据链接") + 1
    for row_idx in range(2, ws.max_row + 1):
        link = ws.cell(row=row_idx, column=link_col).value
        if link:
            cell = ws.cell(row=row_idx, column=link_col)
            cell.hyperlink = link
            cell.font = Font(color="0563C1", underline="single")

    width_map = {
        "姓名*": 12,
        "职务*": 50,
        "老数据职务": 55,
        "排序*": 8,
        "职级*": 14,
        "所属省*": 14,
        "所属市": 12,
        "依据链接": 45,
        "依据说明": 45,
        "维护人": 10,
        "机构": 28,
    }
    for idx, col_name in enumerate(columns, start=1):
        ws.column_dimensions[chr(64 + idx)].width = width_map[col_name]

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap_alignment

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{chr(64 + len(columns))}{ws.max_row}"
    workbook.save(output_path)


def main(
    reminders_path: str | Path,
    normalized_path: str | Path,
    xlsx_filtered_path: str | Path,
    log_path: str | Path,
) -> None:
    """统一入口：读取两个源文件，生成无重复规范化 XLSX。"""
    reminders_path = resolve_path_argument(reminders_path, anchor=__file__)
    normalized_path = resolve_path_argument(normalized_path, anchor=__file__)
    xlsx_filtered_path = resolve_path_argument(xlsx_filtered_path, anchor=__file__)
    log_path = resolve_path_argument(log_path, anchor=__file__)
    log_path = timestamped_output_path(log_path)
    setup_logging(log_path)
    if not reminders_path.is_file():
        logging.error("更新提醒表不存在：%s", reminders_path)
        raise SystemExit(1)
    if not normalized_path.is_file():
        logging.error("重要人物规范化表不存在：%s", normalized_path)
        raise SystemExit(1)
    logging.info("更新提醒表：%s", reminders_path)
    logging.info("重要人物规范化表：%s", normalized_path)

    rh, rrows = read_tsv(reminders_path)
    nh, nrows = read_tsv(normalized_path)
    ri = {name: i for i, name in enumerate(rh)}
    ni = {name: i for i, name in enumerate(nh)}
    for required in ["姓名", "本地职务", "职级", "排序", "依据链接", "提醒类型", "老数据职务"]:
        if required not in ri:
            raise ValueError(f"更新提醒表缺少字段：{required}")
    for required in ["姓名*", "职务*", "排序*", "职级*", "所属省*", "所属市", "依据链接", "依据说明", "维护人", "机构"]:
        if required not in ni:
            raise ValueError(f"规范化表缺少字段：{required}")

    out_rows, unmatched, mode_counts = build_linked_rows(rrows, ri, nrows, ni)
    kept_rows = prepare_filtered_rows(out_rows)
    write_xlsx(kept_rows, xlsx_filtered_path, "无重复排序")
    kept_count = len(kept_rows)
    excluded_count = len(out_rows) - kept_count

    logging.info("更新提醒行数：%d", len(rrows))
    logging.info("关联方式统计：%s", mode_counts)
    logging.info("未匹配行数：%d，姓名：%s", len(unmatched), unmatched)
    logging.info("最终 xlsx 已写出：%s", xlsx_filtered_path)
    logging.info("筛选结果：保留 %d 行，排除 %d 行", kept_count, excluded_count)

    type_counts: dict[str, int] = {}
    for row in out_rows:
        if not has_overlap(row["职务*"], row["老数据职务"]):
            type_counts[row["_提醒类型"]] = type_counts.get(row["_提醒类型"], 0) + 1
    logging.info("保留行提醒类型分布：%s", type_counts)

    category_counts: dict[str, int] = {}
    for row in out_rows:
        if not has_overlap(row["职务*"], row["老数据职务"]):
            cat = classify_org(row["机构"])
            category_counts[cat] = category_counts.get(cat, 0) + 1
    logging.info("保留行机构类别分布：%s", category_counts)

    print(f"输出文件：{xlsx_filtered_path}")
    print(f"保留 {kept_count} 行，排除 {excluded_count} 行")


if __name__ == "__main__":
    reminders_path_value = r"important_people/职务比对3：无重复数据.txt"
    normalized_path_value = r"important_people/职务规范4：扩充.txt"
    xlsx_filtered_path_value = r"important_people/职务比对4：无重复数据规范化.xlsx"
    log_path_value = r"important_people/workspace/log/职务比对/生成规范化复核表.log"
    main(
        reminders_path_value,
        normalized_path_value,
        xlsx_filtered_path_value,
        log_path_value,
    )
