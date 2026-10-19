from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import Tag

from crawler_core.models import PersonRecord
from crawler_core.utils import clean_name, compact_text
from crawler_core.wordlist_filters import (
    is_bad_duty_for_weak_structure,
    is_bad_name_for_weak_structure,
)


ROLE_WORD_PATTERN = re.compile(
    r"(书记|副书记|主席|副主席|主任|副主任|局长|副局长|厅长|副厅长|部长|副部长|"
    r"司长|副司长|"
    r"院长|副院长|秘书长|副秘书长|委员|党组成员|党委委员|负责人|法定代表人|"
    r"组长|副组长|"
    r"巡视员|一级巡视员|二级巡视员|调研员|一级调研员|二级调研员|督学|总工程师|总审计师|"
    r"省长|副省长|市长|副市长|县长|副县长|区长|副区长|馆长|所长|站长|"
    r"队长|社长|校长|处长|科长|会长|副会长|理事长|副理事长|团长|台长|庭长|副庭长|干部|职员|专员|"
    r"巡视员|督察专员|总经理|董事长|监事长|总编辑|总工程师|总会计师|总经济师)"
)

COURT_INLINE_ROLE_HEADER_PATTERN = re.compile(
    r"(?:庭长|副庭长|专职党务干部|主任|副主任|所长|副所长|局长|副局长|"
    r"部长|副部长|总工程师|院长|副院长|社长|副社长|会长|副会长|"
    r"秘书长|副秘书长|组长|副组长)\s*[:：]"
)


INVALID_SELECTOR_HINTS = (
    "角色关键词",
    "fallback",
    "语义识别",
    "同一行",
    "相邻",
    "冒号后",
    "冒号前",
)


def safe_select(node: Any, selector: str) -> list[Any]:
    """执行明确 CSS 选择器；中文说明型 selector 直接视为无效。"""
    selector = str(selector or "").strip()
    if not selector:
        return []
    if any(hint in selector for hint in INVALID_SELECTOR_HINTS):
        return []
    try:
        return list(node.select(selector))
    except Exception:
        return []


def dedupe_records(rows: list[PersonRecord]) -> list[PersonRecord]:
    result: list[PersonRecord] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row.name, row.duty, row.detail_url)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def make_record(
    rule: dict[str, Any],
    name: str,
    duty: str,
    evidence: str,
    parser: str,
    detail_url: str = "",
    snapshot_path: Path | None = None,
    apply_weak_wordlist: bool = False,
) -> PersonRecord | None:
    """构造记录。强结构默认不调用黑白名单。"""
    v3_dir = Path(__file__).resolve().parents[1]
    raw_name = str(name or "").strip()
    raw_duty = compact_text(str(duty or ""))
    clean_person_name = clean_name(raw_name, v3_dir)
    if not clean_person_name or not raw_duty:
        return None
    if apply_weak_wordlist:
        if is_bad_name_for_weak_structure(clean_person_name):
            return None
        if is_bad_duty_for_weak_structure(raw_duty):
            return None
    return PersonRecord(
        organization=str(rule.get("organization", "")),
        url=str(rule.get("url", "")),
        name=clean_person_name,
        duty=raw_duty,
        detail_url=detail_url,
        evidence=compact_text(evidence)[:500],
        confidence=str(rule.get("confidence", "待人工判定")),
        parser=parser,
        snapshot_path=str(snapshot_path or ""),
    )


CPPCC_ROLE_TITLES = {
    "主席",
    "副主席",
    "秘书长",
    "副秘书长",
    "主任",
    "副主任",
    "常务委员",
    "委员",
}


def normalize_cppcc_line(value: str) -> str:
    """规范政协页面中的全角空格和职务标题。"""
    text = compact_text(str(value or "").replace("\u3000", " "))
    text = re.sub(r"\s+", "", text)
    return text.strip()


def clean_cppcc_name_token(value: str) -> str:
    """清理政协名单中的兼职、性别、界别等括注，仅保留姓名。"""
    text = normalize_cppcc_line(value)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    return text.strip()


def is_cppcc_skip_line(value: str) -> bool:
    """判断政协名单区域中不是姓名也不是职务的说明行。"""
    text = normalize_cppcc_line(value)
    if not text:
        return True
    if text in {"办公厅领导", "委员会组成人员", "政协十四届全国委员会"}:
        return True
    if re.fullmatch(r".*委员会组成人员", text):
        return True
    if re.fullmatch(r".*委员会", text) and text not in CPPCC_ROLE_TITLES:
        return True
    if re.fullmatch(r".*领导", text) and text not in CPPCC_ROLE_TITLES:
        return True
    if re.search(r"名|按姓氏笔画排序|界别", text) and text.startswith(("（", "(")):
        return True
    return False


def cppcc_role_group_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """全国政协职务分组名单解析器。"""
    soup = BeautifulSoup(html, "html.parser")
    selector = str(rule.get("leader_region_selector", ""))
    regions = safe_select(soup, selector) or []
    rows: list[PersonRecord] = []
    for region in regions:
        link_map: dict[str, str] = {}
        for link_node in region.select("a[href]"):
            link_name = clean_cppcc_name_token(link_node.get_text(" ", strip=True))
            if link_name:
                link_map.setdefault(link_name, urljoin(final_url or str(rule.get("url", "")), str(link_node.get("href", ""))))
        current_duty = ""
        for raw_line in region.get_text("\n", strip=True).splitlines():
            normalized_line = normalize_cppcc_line(raw_line)
            if re.match(r"^[一二三四五六七八九十]+、", normalized_line):
                current_duty = ""
                continue
            if normalized_line in CPPCC_ROLE_TITLES:
                current_duty = normalized_line
                continue
            if not current_duty or is_cppcc_skip_line(raw_line):
                continue
            name = clean_cppcc_name_token(raw_line)
            if not name:
                continue
            record = make_record(
                rule=rule,
                name=name,
                duty=current_duty,
                evidence=f"{raw_line} {current_duty}",
                parser=str(rule.get("parser", "S019_cppcc_main_role_group_v1")),
                detail_url=link_map.get(name, ""),
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


def parse_strong_css_fields_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """强结构 CSS 字段解析器：禁止依赖黑白名单。"""
    soup = BeautifulSoup(html, "html.parser")
    region_selector = str(rule.get("leader_region_selector", ""))
    name_selector = str(rule.get("name_selector", ""))
    duty_selector = str(rule.get("duty_selector", ""))
    detail_selector = str(rule.get("detail_link_selector", ""))
    regions = safe_select(soup, region_selector) or [soup]
    rows: list[PersonRecord] = []
    if not name_selector or not duty_selector:
        return rows
    for region in regions:
        name_nodes = safe_select(region, name_selector)
        duty_nodes = safe_select(region, duty_selector)
        for index, name_node in enumerate(name_nodes):
            if index >= len(duty_nodes):
                continue
            detail_url = ""
            if detail_selector:
                detail_nodes = safe_select(name_node, detail_selector) or safe_select(region, detail_selector)
                if detail_nodes and getattr(detail_nodes[0], "get", None):
                    detail_url = urljoin(final_url or str(rule.get("url", "")), detail_nodes[0].get("href", ""))
            evidence_node = name_node.parent or region
            record = make_record(
                rule=rule,
                name=name_node.get_text(" ", strip=True),
                duty=duty_nodes[index].get_text(" ", strip=True),
                evidence=evidence_node.get_text(" ", strip=True),
                parser=str(rule.get("parser", "V001_css_field_pair_v1")),
                detail_url=detail_url,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


def normalize_table_label(value: str) -> str:
    """规范表格左侧字段名，兼容“姓 名：”“姓名 :”等写法。"""
    text = compact_text(value)
    text = re.sub(r"[\s\u3000\xa0]+", "", text)
    return text.strip("：:")


def is_table_name_label(value: str) -> bool:
    """判断表格字段是否为姓名。"""
    label = normalize_table_label(value)
    return label in {"姓名", "领导姓名"}


def is_table_duty_label(value: str) -> bool:
    """判断表格字段是否为职务，避免把工作分工误判为职务。"""
    label = normalize_table_label(value)
    return label in {"职务", "现任职务"}


def iter_region_tables(region: Any) -> list[Tag]:
    """获取区域内参与解析的表格，包含区域自身就是 table 的情况。"""
    tables: list[Tag] = []
    if isinstance(region, Tag) and region.name == "table":
        tables.append(region)
    tables.extend(table for table in safe_select(region, "table") if isinstance(table, Tag))
    return tables


def get_direct_row_cells(row: Tag) -> list[Tag]:
    """读取当前表格行的直接单元格，避免嵌套表格污染列判断。"""
    return [
        cell
        for cell in row.find_all(["td", "th"], recursive=False)
        if isinstance(cell, Tag)
    ]


def get_cell_text(cell: Tag) -> str:
    """读取单元格文本并压缩空白。"""
    return compact_text(cell.get_text(" ", strip=True))


def find_first_detail_url(node: Tag, final_url: str, rule: dict[str, Any]) -> str:
    """从当前姓名行内部寻找详情链接，避免误取全页首页链接。"""
    for link_node in node.select("a[href]"):
        href = str(link_node.get("href", "")).strip()
        if not href or href.lower().startswith(("javascript:", "#")):
            continue
        return urljoin(final_url or str(rule.get("url", "")), href)
    return ""


def table_label_value_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """解析“姓名/职务/简历/分工”按标签行重复出现的表格。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    rows: list[PersonRecord] = []
    parser_name = str(rule.get("parser", "V002_table_label_value_v1"))
    for region in regions:
        for table in iter_region_tables(region):
            current_name = ""
            current_duty = ""
            current_detail_url = ""
            evidence_parts: list[str] = []

            def append_current_record() -> None:
                nonlocal current_name, current_duty, current_detail_url, evidence_parts
                record = make_record(
                    rule=rule,
                    name=current_name,
                    duty=current_duty,
                    evidence=" ".join(evidence_parts),
                    parser=parser_name,
                    detail_url=current_detail_url,
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
                current_name = ""
                current_duty = ""
                current_detail_url = ""
                evidence_parts = []

            for table_row in table.select("tr"):
                cells = get_direct_row_cells(table_row)
                while cells and not get_cell_text(cells[0]):
                    cells = cells[1:]
                if len(cells) < 2:
                    continue
                label_text = get_cell_text(cells[0])
                value_text = compact_text(" ".join(get_cell_text(cell) for cell in cells[1:]))
                if is_table_name_label(label_text):
                    append_current_record()
                    current_name = value_text
                    current_detail_url = find_first_detail_url(cells[1], final_url, rule)
                    evidence_parts = [f"{label_text} {value_text}"]
                    continue
                if is_table_duty_label(label_text):
                    current_duty = value_text
                    evidence_parts.append(f"{label_text} {value_text}")
            append_current_record()
    return dedupe_records(rows)


def card_person_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """强结构人物卡片解析器。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    rows: list[PersonRecord] = []
    for region in regions:
        candidates = list(region.select("li")) or list(region.select("div"))
        for node in candidates:
            name_node = node.select_one("h1 a, h2 a, h3 a, h1, h2, h3, .ld_tit, .ldxx_name, .name a, .name")
            duty_node = node.select_one(
                ".ldzw .txt_item, .ldzw p, .ldzw, .ldxx_zw, .job, .duty, .zw, .position, .leader_job, p"
            )
            if not name_node or not duty_node:
                continue
            link_node = name_node if getattr(name_node, "get", None) and name_node.get("href") else node.select_one("a[href]")
            detail_url = urljoin(final_url or str(rule.get("url", "")), link_node.get("href", "")) if link_node else ""
            record = make_record(
                rule=rule,
                name=name_node.get_text(" ", strip=True),
                duty=duty_node.get_text(" ", strip=True),
                evidence=node.get_text(" ", strip=True),
                parser=str(rule.get("parser", "V004_card_person_v1")),
                detail_url=detail_url,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


def clean_hlj_duty_prefix(value: str) -> str:
    """清理黑龙江省政府站领导卡片中保留在职务字段里的标签前缀。"""
    text = compact_text(value)
    text = re.sub(r"^职务(?:（职级）)?\s*[:：]\s*", "", text)
    return text.strip(" ：:")


def hlj_card_person_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """黑龙江省政府站领导卡片解析器，仅清理职务字段前缀，不改变卡片定位逻辑。"""
    rows = card_person_parser_v1(rule, html, final_url, snapshot_path)
    parser_name = str(rule.get("parser", "S024_hlj_card_person_clean_duty_prefix_v1"))
    repaired_rows: list[PersonRecord] = []
    for row in rows:
        row.duty = clean_hlj_duty_prefix(row.duty)
        row.parser = parser_name
        if rule.get("suppress_detail_url"):
            row.detail_url = ""
        if row.name and row.duty:
            repaired_rows.append(row)
    return dedupe_records(repaired_rows)


def strip_leading_name_from_evidence(evidence: str, name: str) -> str:
    """从“姓名 职务”式证据中去掉开头姓名，兼容姓名内部空格。"""
    clean_evidence = compact_text(evidence)
    clean_person_name = normalize_name_for_compare(name)
    if not clean_evidence or not clean_person_name:
        return ""
    name_pattern = r"\s*".join(re.escape(char) for char in clean_person_name)
    return compact_text(re.sub(rf"^\s*{name_pattern}\s*", "", clean_evidence, count=1))


def normalize_name_for_compare(value: str) -> str:
    """仅用于比较姓名与职务是否重复，不调用项目级姓名清洗。"""
    return re.sub(r"\s+", "", str(value or ""))


def chongqing_jgzn_card_name_duty_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """重庆机构职能页人物卡片解析器，修正卡片标题被同时识别为姓名和职务的问题。"""
    rows = card_person_parser_v1(rule, html, final_url, snapshot_path)
    repaired_rows: list[PersonRecord] = []
    for row in rows:
        normalized_name = normalize_name_for_compare(row.name)
        normalized_duty = normalize_name_for_compare(row.duty)
        if normalized_name and normalized_duty == normalized_name:
            repaired_duty = strip_leading_name_from_evidence(row.evidence, row.name)
            if repaired_duty:
                row.duty = repaired_duty
        if row.name and row.duty and normalize_name_for_compare(row.name) != normalize_name_for_compare(row.duty):
            row.parser = str(rule.get("parser", "S023_chongqing_jgzn_card_name_duty_v1"))
            repaired_rows.append(row)
    return dedupe_records(repaired_rows)


def table_person_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """强结构表格解析器，兼容标签-取值表格和明确 CSS 字段。"""
    rows = table_label_value_parser_v1(rule, html, final_url, snapshot_path)
    if rows:
        return rows
    return parse_strong_css_fields_v1(rule, html, final_url, snapshot_path)


COMPOUND_TABLE_SKIP_NAME_PATTERN = re.compile(
    r"(首页|尾页|标题|日期|主办|政策|单位|机构|办公室|处室|内设|专门委员会|"
    r"工作动态|委员会职责|委员会介绍|机构设置|当前位置|索引号|发布机构|有效性|"
    r"来源|中国人大网|研究与报告|法律化|有法|执法|部门网站|版权局|人防办|"
    r"姓名|信箱|政务|人事处|监督投诉|信访与民情|驻院纪检|工程师|审计师|程师|"
    r"法队|店管理处|男汉族|女汉族)"
)


def clean_compound_table_name(value: str) -> str:
    """清理复合表格单元格中的姓名。"""
    text = re.sub(r"[（(][^）)]*(?:女|男|族|兼)[^）)]*[）)]", "", str(value or ""))
    text = re.sub(r"[\s\u3000\u00a0\u2002]+", "", text)
    text = text.strip("：:，,、；;。()（）[]【】")
    return text


def is_compound_table_name(value: str) -> bool:
    """判断复合表格中抽出的姓名是否可信。"""
    name = clean_compound_table_name(value)
    if not name or COMPOUND_TABLE_SKIP_NAME_PATTERN.search(name):
        return False
    if name[:1] in {"长", "员", "记", "视", "的", "及", "为", "书", "研", "程", "计", "法", "店", "助"}:
        return False
    if name.startswith("任") and len(name) > 3:
        return False
    if name.endswith(("处", "科", "室", "局", "厅", "办")):
        return False
    if ROLE_WORD_PATTERN.search(name):
        return False
    return bool(re.fullmatch(r"[一-鿿·]{2,6}", name))


def clean_compound_table_duty(value: str, organization: str = "") -> str:
    """清理复合表格中的职务，截断分工、电话、简历等说明文字。"""
    text = compact_text(value)
    text = re.sub(r"^(?:担任职务|现任职务|职务|职位|岗位|工作履历|个人简历|简历)\s*[:：]\s*", "", text)
    text = re.sub(r"^现任", "", text)
    text = re.sub(r"^[（(]?[一二三四五六七八九十0-9]+[）)]", "", text)
    text = text.replace(">>", "")
    text = text.replace("\u200d", "")
    text = re.split(
        r"(?:职务分工|工作分工|职责分工|领导分工|工作履历|个人简历|简历|分工[:：]|"
        r"办公电话|办公地址|办公时间|基\s*本信息|"
        r"主持|负责|协助|分管|主管|男，|女，|男、|女、|男\s|女\s)",
        text,
        maxsplit=1,
    )[0]
    text = text.strip("：:，,、；;。()（）[]【】 ")
    org = str(organization or "").strip()
    if org and text.startswith(org):
        text = text[len(org):].strip("：:，,、；;。 ")
    if re.search(r"出生|学历|学士|党员|汉族|黎族|研究生", text):
        match = re.search(r"(党委|党组|局党组|厅党组|市委|省委|省政府|市政府|一级|二级|副局|副厅|副主任|副处)", text)
        if match:
            text = text[match.start():]
    return text


def split_compound_duty_name_head(head: str, organization: str = "") -> tuple[str, str]:
    """拆分“职务前缀+姓名”的表格文本。"""
    text = clean_compound_table_duty(head, organization)
    if len(text) > 80:
        return "", ""
    compact = re.sub(r"[\s\u3000\u00a0\u2002]+", "", text)
    for name_length in range(min(4, len(compact)), 1, -1):
        name = clean_compound_table_name(compact[-name_length:])
        if name[:1] in {"长", "员", "记", "视"}:
            continue
        duty = clean_compound_table_duty(compact[:-name_length], organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            return name, duty
    return "", ""


def split_compound_name_duty_text(text: str, organization: str = "") -> list[tuple[str, str, str]]:
    """从一个表格单元格或行文本中抽取“姓名-职务”对。"""
    source = compact_text(str(text or "").replace("\u3000", " ").replace("\u00a0", " ").replace("\u2002", " "))
    if not source or len(source) < 4:
        return []
    source = re.sub(r"[\|｜]+", " ", source)
    results: list[tuple[str, str, str]] = []

    for match in re.finditer(
        r"姓名\s*[:：]\s*(?P<name>[一-鿿·\s]{2,8})\s+"
        r"(?:担任职务|现任职务|职务|职位|岗位)\s*[:：]\s*(?P<duty>.*?)(?=姓名\s*[:：]|$)",
        source,
    ):
        name = clean_compound_table_name(match.group("name"))
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    compact_source = re.sub(r"[\s\u3000\u00a0\u2002]+", "", source)
    for match in re.finditer(
        r"(?P<duty>[^。；，,、]{0,40}(?:书记|副书记|局长|副局长|厅长|副厅长|主任|副主任|"
        r"秘书长|副秘书长|巡视员|调研员|总工程师|总审计师)[^。；，,]{0,30}?)"
        r"(?P<name>[一-鿿·]{2,4})同志",
        compact_source,
    ):
        name = clean_compound_table_name(match.group("name"))
        if name[:1] in {"长", "员", "记", "视"}:
            continue
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    for match in re.finditer(
        r"(?P<name>[一-鿿·\s]{2,8})[，,]\s*(?:男|女)[^。；]{0,220}?(?:现任)?(?P<duty>[^。；]{2,140})[。；]",
        source,
    ):
        name = clean_compound_table_name(match.group("name"))
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    for match in re.finditer(
        r"(?P<name>[一-鿿·\s]{2,8})[，,]\s*(?:男|女)[^。；]{0,220}?[。；]\s*现任(?P<duty>[^。；]{2,140})[。；]",
        source,
    ):
        name = clean_compound_table_name(match.group("name"))
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    for match in re.finditer(
        r"(?P<name>[一-鿿·\s]{2,8})\s+基\s*本信息\s*[:：]\s*(?:男|女)[^。；]{0,220}?现任(?P<duty>[^。；]{2,140})[。；]",
        source,
    ):
        name = clean_compound_table_name(match.group("name"))
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    prefix = re.split(r"(?:职务分工|工作分工|职责分工|分工[:：]|办公电话|办公地址|办公时间)", source, maxsplit=1)[0]
    prefix = prefix.strip(" ，,。；;")
    for match in re.finditer(
        r"(?P<duty>(?:党组|党委|局党组|厅党组|市委|省委|市人大常委会)?[^。；\s]{0,24}?"
        r"(?:书记|副书记|局长|副局长|厅长|副厅长|主任|副主任|秘书长|副秘书长|巡视员|调研员|总工程师)"
        r"(?:、[^。；\s]{1,18}?(?:书记|副书记|局长|副局长|厅长|副厅长|主任|副主任|秘书长|副秘书长|巡视员|调研员|总工程师))*?)"
        r"\s+(?P<name>[一-鿿·\s]{2,8})(?=\s+(?:党组|党委|局党组|厅党组|市委|省委|市人大常委会)?[^。；\s]{0,24}?"
        r"(?:书记|副书记|局长|副局长|厅长|副厅长|主任|副主任|秘书长|副秘书长|巡视员|调研员|总工程师)|$)",
        prefix,
    ):
        name = clean_compound_table_name(match.group("name"))
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    for match in re.finditer(
        r"(?P<name>[一-鿿·\s]{2,8})\s*[（(](?P<duty>[^）)]{2,120})[）)]",
        prefix,
    ):
        name = clean_compound_table_name(match.group("name"))
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    match = re.match(r"(?P<name>[一-鿿·\s]{2,8})\s+(?P<duty>[^。；]{2,160})", prefix)
    if match:
        name = clean_compound_table_name(match.group("name"))
        duty = clean_compound_table_duty(match.group("duty"), organization)
        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
            results.append((name, duty, match.group(0)))

    name, duty = split_compound_duty_name_head(prefix, organization)
    if name and duty:
        results.append((name, duty, prefix))

    deduped: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for name, duty, evidence in results:
        key = (name, duty)
        if key not in seen:
            seen.add(key)
            deduped.append((name, duty, evidence))
    return deduped


def parse_compound_table_lines(region: Tag, organization: str = "") -> list[tuple[str, str, str]]:
    """解析同一正文中相邻行形成的“职务-姓名”关系。"""
    raw_lines = [compact_text(line) for line in region.get_text("\n", strip=True).splitlines()]
    lines = [line for line in raw_lines if line]
    results: list[tuple[str, str, str]] = []
    pending_duty = ""
    for index, line in enumerate(lines):
        clean_line = line.strip(" ：:，,。；;")
        clean_name_line = clean_compound_table_name(clean_line)
        if index + 1 < len(lines) and is_compound_table_name(clean_name_line):
            next_line = lines[index + 1].strip(" ：:，,。；;")
            if re.match(r"^(?:男|女)[，,]", next_line) and "现任" in next_line:
                next_line_for_parse = next_line if next_line.endswith(("。", "；", ";")) else f"{next_line}。"
                for name, duty, evidence in split_compound_name_duty_text(
                    f"{clean_name_line}，{next_line_for_parse}",
                    organization,
                ):
                    results.append((name, duty, evidence))
        for name, duty, evidence in split_compound_name_duty_text(clean_line, organization):
            results.append((name, duty, evidence))
        compact_line = re.sub(r"[\s\u3000\u00a0\u2002]+", "", clean_line)
        if is_compound_table_name(compact_line) and pending_duty:
            results.append((compact_line, pending_duty, f"{pending_duty} {compact_line}"))
            pending_duty = ""
            continue
        if ROLE_WORD_PATTERN.search(clean_line) and len(clean_line) <= 80:
            name, duty = split_compound_duty_name_head(clean_line, organization)
            if name and duty:
                results.append((name, duty, clean_line))
                pending_duty = ""
            elif not re.search(r"分管|负责|主持|工作|委员会|网站|首页", clean_line):
                pending_duty = clean_compound_table_duty(clean_line, organization)
        elif not re.match(r"^[（(]?[一二三四五六七八九十0-9]+[）)]?$", clean_line):
            pending_duty = ""
    deduped: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for name, duty, evidence in results:
        key = (name, duty)
        if key not in seen:
            seen.add(key)
            deduped.append((name, duty, evidence))
    return deduped


def table_compound_person_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """解析表格单元格内“姓名+职务+分工/简介”的强结构页面。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    organization = str(rule.get("organization", ""))
    rows: list[PersonRecord] = []
    parser_name = str(rule.get("parser", "V003_table_compound_person_v1"))
    for region in regions:
        tables = iter_region_tables(region) or []
        candidate_nodes: list[Tag] = []
        for table in tables:
            header: list[str] = []
            for table_row in table.find_all("tr"):
                cells = get_direct_row_cells(table_row)
                cell_texts = [get_cell_text(cell) for cell in cells]
                if not any(cell_texts):
                    continue
                normalized = [normalize_table_label(text) for text in cell_texts]
                if "姓名" in normalized and "职务" in normalized:
                    header = normalized
                    continue
                if header:
                    try:
                        name_index = header.index("姓名")
                        duty_index = header.index("职务")
                    except ValueError:
                        name_index = -1
                        duty_index = -1
                    if 0 <= name_index < len(cells) and 0 <= duty_index < len(cells):
                        name = clean_compound_table_name(cell_texts[name_index])
                        duty = clean_compound_table_duty(cell_texts[duty_index], organization)
                        if is_compound_table_name(name) and ROLE_WORD_PATTERN.search(duty):
                            detail_url = find_first_detail_url(cells[name_index], final_url, rule)
                            record = make_record(
                                rule=rule,
                                name=name,
                                duty=duty,
                                evidence=" ".join(cell_texts),
                                parser=parser_name,
                                detail_url=detail_url,
                                snapshot_path=snapshot_path,
                                apply_weak_wordlist=False,
                            )
                            if record:
                                rows.append(record)
                candidate_nodes.append(table_row)
                candidate_nodes.extend(cells)
        if not candidate_nodes and isinstance(region, Tag):
            candidate_nodes = list(region.find_all(["p", "li", "div"], recursive=True))[:500]
        elif isinstance(region, Tag):
            candidate_nodes.extend(list(region.find_all(["p", "li"], recursive=True))[:500])
        for node in candidate_nodes:
            text = get_cell_text(node)
            if len(text) > 3000:
                continue
            for name, duty, evidence in split_compound_name_duty_text(text, organization):
                record = make_record(
                    rule=rule,
                    name=name,
                    duty=duty,
                    evidence=evidence,
                    parser=parser_name,
                    detail_url=find_first_detail_url(node, final_url, rule),
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
        if isinstance(region, Tag):
            for name, duty, evidence in parse_compound_table_lines(region, organization):
                record = make_record(
                    rule=rule,
                    name=name,
                    duty=duty,
                    evidence=evidence,
                    parser=parser_name,
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
    best_rows: dict[tuple[str, str], PersonRecord] = {}
    for row in rows:
        key = (row.name, row.duty)
        current = best_rows.get(key)
        if current is None or (row.detail_url and not current.detail_url):
            best_rows[key] = row
    return list(best_rows.values())


def fuzhou_xinfang_leader_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """福州市信访局领导分工页解析器，处理职务和姓名被正文换行拆开的情况。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    organization = str(rule.get("organization", ""))
    parser_name = str(rule.get("parser", "S020_fuzhou_xinfang_name_duty_split_v1"))
    rows: list[PersonRecord] = []

    def add_record(name: str, duty: str, evidence: str) -> None:
        record = make_record(
            rule=rule,
            name=clean_compound_table_name(name),
            duty=clean_compound_table_duty(duty, organization),
            evidence=evidence,
            parser=parser_name,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    for region in regions:
        lines = [compact_text(line) for line in region.get_text("\n", strip=True).splitlines()]
        pending_duty = ""
        for raw_line in lines:
            line = re.sub(r"^[（(]?[一二三四五六七八九十0-9]+[）)]", "", raw_line).strip(" ：:，,。；;")
            if not line or COMPOUND_TABLE_SKIP_NAME_PATTERN.search(line):
                continue
            line = line.replace("）", "").replace(")", "")
            compact_line = re.sub(r"[\s\u3000\u00a0\u2002]+", "", line)
            if re.search(r"职责|分工|负责|接待|办理|科室|公开", compact_line):
                continue

            if pending_duty:
                separator = "、" if re.match(r"^(?:一|二|三|四)?级?(?:巡视员|调研员)", compact_line) else ""
                combined = pending_duty + separator + compact_line.lstrip("、，,")
                name, duty = split_compound_duty_name_head(combined, organization)
                if name and duty:
                    add_record(name, duty, combined)
                    pending_duty = ""
                    continue
                if is_compound_table_name(compact_line):
                    add_record(compact_line, pending_duty, f"{pending_duty} {compact_line}")
                    pending_duty = ""
                    continue

            name, duty = split_compound_duty_name_head(compact_line, organization)
            if name and duty:
                add_record(name, duty, compact_line)
                pending_duty = ""
                continue
            if ROLE_WORD_PATTERN.search(compact_line) and len(compact_line) <= 40:
                pending_duty = clean_compound_table_duty(compact_line, organization)
            else:
                pending_duty = ""
    return dedupe_records(rows)


def cas_leader_group_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """中国科学院院领导集体解析器，处理姓名后跟多行职务的页面。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    text = "\n".join(region.get_text("\n", strip=True) for region in regions)
    if "院领导集体" in text:
        text = text.rsplit("院领导集体", 1)[1]
    if "机构设置" in text:
        text = text.split("机构设置", 1)[0]
    lines = [compact_text(line) for line in re.split(r"[\r\n]+", text)]
    lines = [line for line in lines if line]
    rows: list[PersonRecord] = []
    current_name = ""
    duty_parts: list[str] = []
    parser_name = str(rule.get("parser", "S021_cas_main_leader_group_v1"))

    def flush() -> None:
        nonlocal current_name, duty_parts
        if not current_name or not duty_parts:
            current_name = ""
            duty_parts = []
            return
        duty = "；".join(duty_parts)
        duty = duty.replace("驻院纪检、监察组组长", "驻院纪检监察组组长")
        record = make_record(
            rule=rule,
            name=current_name,
            duty=duty,
            evidence=f"{current_name} {duty}",
            parser=parser_name,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
        current_name = ""
        duty_parts = []

    for line in lines:
        name_candidate = clean_compound_table_name(line)
        if is_compound_table_name(name_candidate) and not ROLE_WORD_PATTERN.search(name_candidate):
            flush()
            current_name = name_candidate
            continue
        if not current_name:
            continue
        if re.search(r"^\(?正?副?部?长级\)?$", line):
            continue
        if line == "驻院纪检" or ROLE_WORD_PATTERN.search(line):
            duty_parts.append(line)
    flush()
    return dedupe_records(rows)


def npc_committee_role_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """解析全国人大委员会页面中的“主任/副主任/委员”名单文本。"""
    text = get_region_text(rule, html)
    text = compact_text(text.replace("委 员", "委员"))
    if "会议通过）" in text:
        text = text.split("会议通过）", 1)[1]
    if "四、现任领导" in text:
        text = text.split("四、现任领导", 1)[1]
    if "现任预算工作委员会主任" in text:
        text = text.split("现任预算工作委员会主任", 1)[1]
        text = "预算工作委员会主任" + text
    rows: list[PersonRecord] = []
    parser_name = str(rule.get("parser", "S022_npc_main_committee_role_list_v1"))

    patterns = [
        (r"(?<!副)主任委员\s*(?P<names>.+?)(?=副主任委员|委员\s|编 辑|编辑|责 编|$)", "主任委员"),
        (r"副主任委员\s*(?P<names>.+?)(?=委员\s|编辑|责 编|$)", "副主任委员"),
        (r"现任主任[:：]\s*(?P<names>.+?)(?=现任副主任|编辑|责 编|$)", "主任"),
        (r"现任副主任[:：]\s*(?P<names>.+?)(?=编辑|责 编|$)", "副主任"),
        (r"预算工作委员会主任(?P<names>[一-鿿·]{2,8})", "主任"),
        (r"副主任是(?P<names>.+?)(?=。|编辑|责 编|$)", "副主任"),
    ]
    if "主任委员" in text and "副主任委员" in text:
        patterns.insert(2, (r"委员\s*(?:（[^）]+）)?\s*(?P<names>.+?)(?=编 辑|编辑|责 编|$)", "委员"))
    for pattern, duty in patterns:
        for match in re.finditer(pattern, text):
            names_text = re.sub(r"[（(][^）)]*[）)]", "", match.group("names"))
            names_text = re.sub(r"(来源|中国人大网|浏览字号|大|中|小|年|月|日|当前位置|首页)", " ", names_text)
            names_text = re.sub(r"、", " ", names_text)
            for name in split_person_names(names_text):
                clean_person = clean_compound_table_name(name)
                if not is_compound_table_name(clean_person):
                    continue
                record = make_record(
                    rule=rule,
                    name=clean_person,
                    duty=duty,
                    evidence=f"{duty} {clean_person}",
                    parser=parser_name,
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
    return dedupe_records(rows)



def zhejiang_department_leader_card_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """浙江省部门页领导卡片解析器，按单个领导块抽取姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    rows: list[PersonRecord] = []
    for region in regions:
        cards = safe_select(region, str(rule.get("card_selector", ""))) or safe_select(region, ".ldtxt_box")
        for card in cards:
            if not isinstance(card, Tag):
                continue
            name_node = card.select_one(str(rule.get("name_selector") or ".ld_tit"))
            duty_node = card.select_one(str(rule.get("duty_selector") or ".jg_ldxx_item.ldzw .txt_item"))
            if not name_node or not duty_node:
                continue
            link_node = card.find_parent("a", href=True) or card.select_one("a[href]")
            detail_url = ""
            if link_node:
                detail_url = urljoin(final_url or str(rule.get("url", "")), str(link_node.get("href", "")))
            evidence_node = card.find_parent("li") or card
            record = make_record(
                rule=rule,
                name=name_node.get_text(" ", strip=True),
                duty=duty_node.get_text(" ", strip=True),
                evidence=evidence_node.get_text(" ", strip=True),
                parser=str(rule.get("parser", "S001_zhejiang_gov_department_leader_card_v1")),
                detail_url=detail_url,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


def zhejiang_government_leader_group_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """浙江省政府领导分组页解析器，按分组标题绑定后续姓名列表。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    rows: list[PersonRecord] = []
    for region in regions:
        for leader_box in safe_select(region, ".list_leader"):
            current_duty = ""
            for child in getattr(leader_box, "children", []):
                if not isinstance(child, Tag):
                    continue
                child_classes = child.get("class", [])
                if "list_leader_t" in child_classes:
                    current_duty = compact_text(child.get_text(" ", strip=True))
                    continue
                if "list_leader_b" not in child_classes or not current_duty:
                    continue
                for link_node in child.select("li a[href]"):
                    name_node = link_node.select_one("span") or link_node
                    record = make_record(
                        rule=rule,
                        name=name_node.get_text(" ", strip=True),
                        duty=current_duty,
                        evidence=f"{current_duty} {link_node.get_text(' ', strip=True)}",
                        parser=str(rule.get("parser", "S002_zhejiang_gov_leader_group_v1")),
                        detail_url=urljoin(final_url or str(rule.get("url", "")), str(link_node.get("href", ""))),
                        snapshot_path=snapshot_path,
                        apply_weak_wordlist=False,
                    )
                    if record:
                        rows.append(record)
    return dedupe_records(rows)


HANGZHOU_EXTRA_ROLE_PATTERN = re.compile(r"(常委|政委)")


def clean_hangzhou_name(value: str) -> str:
    """清理杭州站点姓名中用于排版的全角空格。"""
    text = compact_text(str(value or "").replace("\u3000", " "))
    return re.sub(r"\s+", "", text)


def has_hangzhou_role_word(value: str) -> bool:
    """判断杭州党政领导列表中的职务文本是否可信。"""
    text = compact_text(value)
    return bool(ROLE_WORD_PATTERN.search(text) or HANGZHOU_EXTRA_ROLE_PATTERN.search(text))


def parse_hangzhou_link_text(value: str) -> tuple[str, str]:
    """解析“刘　非 省委常委 市委书记”一类链接文本。"""
    text = compact_text(str(value or "").replace("\u3000", " "))
    parts = [part for part in text.split(" ") if part]
    if len(parts) < 2:
        return "", ""
    if len(parts[0]) == 1 and len(parts) >= 3 and len(parts[1]) == 1:
        name = parts[0] + parts[1]
        duty_parts = parts[2:]
    else:
        name = parts[0]
        duty_parts = parts[1:]
    duty = compact_text(" ".join(duty_parts))
    if not re.fullmatch(r"[一-鿿·]{2,8}", clean_hangzhou_name(name)):
        return "", ""
    if not has_hangzhou_role_word(duty):
        return "", ""
    return clean_hangzhou_name(name), duty


def hangzhou_leader_team_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """杭州政府网站领导班子解析器，兼容部门页卡片和党政领导专题页侧栏。"""
    soup = BeautifulSoup(html, "html.parser")
    selector = str(rule.get("leader_region_selector", ""))
    regions = safe_select(soup, selector) or safe_select(soup, "#con_one_2") or safe_select(soup, ".sidenav")
    rows: list[PersonRecord] = []
    for region in regions:
        cards = safe_select(region, ".jgzn")
        if cards:
            for card in cards:
                lines = [compact_text(line) for line in card.get_text("\n", strip=True).splitlines()]
                lines = [line for line in lines if line and line not in {"领导简历：", "工作分工："}]
                if len(lines) < 2:
                    continue
                name = clean_hangzhou_name(lines[0])
                duty = compact_text(lines[1])
                if not re.fullmatch(r"[一-鿿·]{2,8}", name) or not has_hangzhou_role_word(duty):
                    continue
                record = make_record(
                    rule=rule,
                    name=name,
                    duty=duty,
                    evidence=f"{name} {duty}",
                    parser=str(rule.get("parser", "S003_hangzhou_gov_leader_team_v1")),
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
            continue

        for link_node in safe_select(region, "li a[href]"):
            name, duty = parse_hangzhou_link_text(link_node.get_text(" ", strip=True))
            if not name or not duty:
                continue
            href = str(link_node.get("href", "")).strip()
            detail_url = ""
            if href and not href.lower().startswith(("javascript:", "#")):
                detail_url = urljoin(final_url or str(rule.get("url", "")), href)
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=f"{name} {duty}",
                parser=str(rule.get("parser", "S003_hangzhou_gov_leader_team_v1")),
                detail_url=detail_url,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


MFA_STOP_LABELS = {"主要职责", "主要职责：", "简介", "简介：", "电话", "电话：", "传真", "传真："}


def normalize_mfa_label(value: str) -> str:
    """规范外交部司局页中的职务标签。"""
    text = str(value or "")
    text = re.sub(r"[\s\u3000\u2002\u2003\xa0]+", "", text)
    return text.strip("：:")


def normalize_mfa_name_token(value: str) -> str:
    """规范外交部半结构姓名字段，仅去除括注、排版空白和不可见字符。"""
    text = str(value or "")
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.sub(r"[\s\u3000\u2002\u2003\xa0\u200b\u200c\u200d\ufeff]+", "", text)
    return text.strip()


def split_mfa_names(value: str) -> list[str]:
    """拆分外交部司局页同一职务下的多人姓名。"""
    names: list[str] = []
    for part in re.split(r"[、,，/／]+", str(value or "")):
        name = normalize_mfa_name_token(part)
        if re.fullmatch(r"[一-鿿·]{2,8}", name):
            names.append(name)
    return names


def make_mfa_record(
    rule: dict[str, Any],
    name: str,
    duty: str,
    evidence: str,
    parser: str,
    detail_url: str = "",
    snapshot_path: Path | None = None,
) -> PersonRecord | None:
    """外交部半结构字段专用记录构造，不使用通用姓名黑名单。"""
    clean_person_name = normalize_mfa_name_token(name)
    clean_duty = compact_text(duty)
    if not re.fullmatch(r"[一-鿿·]{2,8}", clean_person_name) or not clean_duty:
        return None
    return PersonRecord(
        organization=str(rule.get("organization", "")),
        url=str(rule.get("url", "")),
        name=clean_person_name,
        duty=clean_duty,
        detail_url=detail_url,
        evidence=compact_text(evidence)[:500],
        confidence=str(rule.get("confidence", "待人工判定")),
        parser=parser,
        snapshot_path=str(snapshot_path or ""),
    )


def iter_mfa_info_lines(region: Tag) -> list[str]:
    """按字段块读取 .clearfix 内文本，避免把职责正文继续纳入。"""
    lines: list[str] = []
    content_region = region.select_one(".desc") or region
    for node in content_region.find_all(["div", "p", "li"], recursive=True):
        if not isinstance(node, Tag):
            continue
        if node.find(["div", "p", "li"]):
            continue
        line = compact_text(node.get_text(" ", strip=True))
        if line:
            lines.append(line)
    if not lines:
        lines = [compact_text(line) for line in region.get_text("\n", strip=True).splitlines() if compact_text(line)]
    return lines


def parse_mfa_info_region(
    rule: dict[str, Any],
    region: Tag,
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """解析外交部司局页“主要职责”之前的职务姓名字段。"""
    rows: list[PersonRecord] = []
    for line in iter_mfa_info_lines(region):
        label_part, separator, names_part = line.partition("：")
        if not separator:
            label_part, separator, names_part = line.partition(":")
        label = normalize_mfa_label(label_part)
        if not label:
            continue
        if label in MFA_STOP_LABELS or label.startswith(("主要职责", "简介", "电话", "传真")):
            break
        if not separator or not names_part.strip():
            continue
        if not has_hangzhou_role_word(label):
            continue
        for name in split_mfa_names(names_part):
            record = make_mfa_record(
                rule=rule,
                name=name,
                duty=label,
                evidence=f"{label}：{name}",
                parser=str(rule.get("parser", "S004_mfa_main_leader_info_v1")),
                snapshot_path=snapshot_path,
            )
            if record:
                rows.append(record)
    return rows


def fetch_mfa_detail_duty(detail_url: str, name: str) -> tuple[str, str]:
    """读取外交部部领导详情页首部职务信息。"""
    try:
        import requests
    except Exception:
        return "", ""
    try:
        response = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        response.encoding = response.apparent_encoding
    except Exception:
        return "", ""
    soup = BeautifulSoup(response.text, "html.parser")
    region = soup.select_one(".about-details.clearfix, .main.clearfix, .main")
    if not region:
        return "", ""
    lines = [compact_text(line) for line in region.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    duty_parts: list[str] = []
    bio_line = ""
    for line in lines:
        clean_line = compact_text(line)
        compact_line = clean_line.replace(" ", "")
        if name and name in compact_line:
            bio_line = clean_line
            break
        if clean_line in {"相关新闻", "详细内容"} or re.search(r"\(\d{4}-\d{2}-\d{2}\)", clean_line):
            break
        if has_hangzhou_role_word(clean_line):
            duty_parts.append(clean_line)
        elif duty_parts and clean_line.startswith(("（", "(")):
            duty_parts.append(clean_line)
        elif duty_parts:
            break
    duty = compact_text("".join(duty_parts))
    return duty, compact_text(f"{duty} {bio_line}")


def parse_mfa_leader_cards(
    rule: dict[str, Any],
    region: Tag,
    final_url: str,
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """解析外交部部领导图片列表，并从详情页补职务。"""
    rows: list[PersonRecord] = []
    base_url = final_url or str(rule.get("url", ""))
    for link_node in region.select("li a[href]"):
        name_node = link_node.select_one("span") or link_node
        name = normalize_mfa_name_token(name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[一-鿿·]{2,8}", name):
            continue
        detail_url = urljoin(base_url, str(link_node.get("href", "")).strip())
        duty, detail_evidence = fetch_mfa_detail_duty(detail_url, name)
        if not duty:
            continue
        record = make_mfa_record(
            rule=rule,
            name=name,
            duty=duty,
            evidence=detail_evidence or f"{name} {duty}",
            parser=str(rule.get("parser", "S004_mfa_main_leader_info_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
        )
        if record:
            rows.append(record)
    return rows


def mfa_leader_info_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """外交部官网主要官员解析器，限定在 .clearfix 内职责说明之前。"""
    soup = BeautifulSoup(html, "html.parser")
    selector = str(rule.get("leader_region_selector", ""))
    regions = safe_select(soup, selector) or safe_select(soup, ".main .clearfix")
    rows: list[PersonRecord] = []
    for region in regions:
        if region.select_one(".desc") or re.search(r"[：:]", region.get_text(" ", strip=True)):
            rows.extend(parse_mfa_info_region(rule, region, snapshot_path))
        if not rows:
            rows.extend(parse_mfa_leader_cards(rule, region, final_url, snapshot_path))
    return dedupe_records(rows)


HARBIN_INLINE_ROLE_PATTERN = re.compile(
    r"(党组书记|党委书记|书记|副书记|局长|副局长|主任|副主任|二级巡视员|一级巡视员|"
    r"专职副书记|党委专职副书记|党组成员|党委委员|总工程师|机关党委书记|市长|副市长)"
)


def clean_harbin_text(value: str) -> str:
    """规范哈尔滨页面中的空格和不可见分隔符。"""
    text = str(value or "").replace("\u3000", " ").replace("\u00a0", " ").replace("\u2002", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(书)\s+(记)", r"\1\2", text)
    return text.strip()


def clean_harbin_name(value: str) -> str:
    """清理正文段落开头的人名。"""
    text = re.sub(r"[（(][^）)]*[）)]", "", str(value or ""))
    text = re.sub(r"^\s*\d+\s*[.．、]\s*", "", text)
    text = re.sub(r"同志$", "", text.strip())
    text = re.sub(r"[\s\u3000\u00a0\u2002]+", "", text)
    return text.strip("：:,，。；;")


def clean_harbin_duty(value: str, organization: str = "") -> str:
    """清理哈尔滨正文中的职务文本，保留机构前缀但截去简历或分工。"""
    text = clean_harbin_text(value)
    text = re.sub(r"^[，,。；;：:\s]+", "", text)
    if "现任" in text:
        text = text.split("现任", 1)[1]
    text = re.split(r"(?:。|；|;|负责|主持|分管|协助|工作简历|工作分工)", text, maxsplit=1)[0]
    text = text.strip("，,。；;：: ")
    org = str(organization or "").strip()
    if org and text.startswith(org):
        text = text[len(org):].strip("，,。；;：: ")
    text = re.sub(r"\s*([、，,])\s*", r"\1", text)
    return text


def is_harbin_name(value: str) -> bool:
    """判断是否为可信中文姓名。"""
    name = clean_harbin_name(value)
    if name in {"工作简历", "工作分工", "领导信息", "领导简介", "局领导介绍"}:
        return False
    if re.search(r"党委|党组|领导|分管|协助|负责", name):
        return False
    if ROLE_WORD_PATTERN.search(name) or HARBIN_INLINE_ROLE_PATTERN.search(name):
        return False
    return bool(re.fullmatch(r"[一-鿿·]{2,8}", name))


def is_harbin_duty(value: str) -> bool:
    """判断是否包含职务词。"""
    return bool(HARBIN_INLINE_ROLE_PATTERN.search(clean_harbin_text(value)) or ROLE_WORD_PATTERN.search(value))


def split_harbin_duty_name_head(head: str, organization: str = "") -> tuple[str, str]:
    """拆分“职务前缀+姓名”的段落头部。"""
    compact = re.sub(r"[\s\u2002\u00a0\u3000]+", "", clean_harbin_text(head))
    compact = re.sub(r"同志$", "", compact)
    for name_length in range(min(4, len(compact)), 1, -1):
        name = clean_harbin_name(compact[-name_length:])
        if name[:1] in {"长", "任", "助", "组", "记", "员"}:
            continue
        duty = clean_harbin_duty(compact[:-name_length], organization)
        if is_harbin_name(name) and is_harbin_duty(duty):
            return name, duty
    return "", ""


def collect_harbin_content_lines(region: Tag) -> list[str]:
    """收集 detail_info 正文块中的候选段落，跳过元数据、字号和图片空段。"""
    content = region.select_one("#detailContent, .detailContent") or region
    nodes = content.find_all(["h1", "h2", "h3", "h4", "p", "div"], recursive=True)
    lines: list[str] = []
    for node in nodes:
        if not isinstance(node, Tag):
            continue
        if node.find(["p", "div"]):
            continue
        line = clean_harbin_text(node.get_text(" ", strip=True))
        if not line:
            continue
        if line in {"字号： 大 中 小", "大 中 小", "分享到：", "相关文章", "扫一扫在手机打开当前页"}:
            continue
        if re.fullmatch(r"[\s\-—_]*", line):
            continue
        lines.append(line)
    if not lines:
        lines = [clean_harbin_text(line) for line in content.get_text("\n", strip=True).splitlines()]
        lines = [line for line in lines if line]
    return lines


def parse_harbin_line(line: str, organization: str = "") -> tuple[str, str, str]:
    """从哈尔滨正文段落开头解析姓名和职务。"""
    text = clean_harbin_text(line)
    text = re.sub(r"^\s*\d+\s*[.．、]\s*", "", text)
    if not text or "互为AB角" in text or "AB角" in text:
        return "", "", ""
    if text.startswith(("工作简历", "工作分工", "负责", "分管", "主持", "日期：", "来源：")):
        return "", "", ""

    match = re.match(r"(?P<head>[^。；;\n:：]{4,100})(?:同志)?\s*[:：]\s*", text)
    if match:
        name, duty = split_harbin_duty_name_head(match.group("head"), organization)
        if name and duty:
            return name, duty, f"{name} {duty}"

    match = re.match(r"(?P<name>[一-鿿·\s\u2002\u00a0]{2,12})\s*[:：]\s*(?P<duty>[^。；;\n]{2,120})", text)
    if match:
        name = clean_harbin_name(match.group("name"))
        duty = clean_harbin_duty(match.group("duty"), organization)
        if is_harbin_name(name) and is_harbin_duty(duty):
            return name, duty, f"{name}：{duty}"

    match = re.match(r"(?P<name>[一-鿿·]{2,8})[，,]\s*.*?现任(?P<duty>[^。；;\n]{2,160})", text)
    if match:
        name = clean_harbin_name(match.group("name"))
        duty = clean_harbin_duty(match.group("duty"), organization)
        if is_harbin_name(name) and is_harbin_duty(duty):
            return name, duty, f"{name} {duty}"

    match = re.match(r"(?P<name>[一-鿿·]{2,8})[，,]\s*(?P<duty>[^。；;\n]{2,160})", text)
    if match and not re.match(r"[男女][，,]", match.group("duty")):
        name = clean_harbin_name(match.group("name"))
        duty = clean_harbin_duty(match.group("duty"), organization)
        if is_harbin_name(name) and is_harbin_duty(duty):
            return name, duty, f"{name} {duty}"

    match = re.match(r"(?P<head>[^。；;\n]{4,140}?)同志\s*(?:负责|主持|协助|分管|。|，|,|；|;)", text)
    if match:
        name, duty = split_harbin_duty_name_head(match.group("head"), organization)
        if name and duty:
            return name, duty, f"{name} {duty}"

    split_parts = [part for part in re.split(r"[\s\u2002\u00a0\u3000]{2,}", text) if clean_harbin_text(part)]
    if len(split_parts) >= 2:
        possible_name = clean_harbin_name(split_parts[-1])
        possible_duty = clean_harbin_duty(" ".join(split_parts[:-1]), organization)
        if is_harbin_name(possible_name) and is_harbin_duty(possible_duty):
            return possible_name, possible_duty, f"{possible_name} {possible_duty}"

    match = re.match(r"(?P<duty>[^。；;\n]{2,80})\s+(?P<name>[一-鿿·\s\u2002\u00a0]{2,12})$", text)
    if match:
        name = clean_harbin_name(match.group("name"))
        duty = clean_harbin_duty(match.group("duty"), organization)
        if is_harbin_name(name) and is_harbin_duty(duty):
            return name, duty, f"{name} {duty}"

    match = re.match(r"(?P<name>[一-鿿·\s\u2002\u00a0]{2,12})\s+(?P<duty>[^。；;\n]{2,120})", text)
    if match:
        name = clean_harbin_name(match.group("name"))
        duty = clean_harbin_duty(match.group("duty"), organization)
        if is_harbin_name(name) and is_harbin_duty(duty):
            return name, duty, f"{name} {duty}"

    compact = re.sub(r"[\s\u2002\u00a0\u3000]+", "", text)
    for name_length in range(2, min(5, len(compact)) + 1):
        name = compact[:name_length]
        rest = compact[name_length:]
        role_match = HARBIN_INLINE_ROLE_PATTERN.match(rest)
        if not role_match:
            continue
        duty = clean_harbin_duty(rest, organization)
        if is_harbin_name(name) and is_harbin_duty(duty):
            return name, duty, f"{name} {duty}"

    return "", "", ""


def harbin_detail_info_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """哈尔滨 detail_info 正文段落开头领导信息解析器。"""
    soup = BeautifulSoup(html, "html.parser")
    selector = str(rule.get("leader_region_selector", ""))
    regions = safe_select(soup, selector) or safe_select(soup, "#detailContent") or safe_select(soup, ".detail_info")
    rows: list[PersonRecord] = []
    organization = str(rule.get("organization", ""))
    for region in regions:
        pending_name = ""
        for line in collect_harbin_content_lines(region):
            name, duty, evidence = parse_harbin_line(line, organization)
            if not name and pending_name:
                pending_duty = ""
                if "现任" in line:
                    pending_duty = clean_harbin_duty(line, organization)
                elif is_harbin_duty(line) and not line.startswith(("工作简历", "工作分工")):
                    pending_duty = clean_harbin_duty(line, organization)
                if pending_duty and is_harbin_duty(pending_duty):
                    name = pending_name
                    duty = pending_duty
                    evidence = f"{name} {duty}"
                    pending_name = ""
            if not name:
                possible_name = clean_harbin_name(line)
                if is_harbin_name(possible_name):
                    pending_name = possible_name
                elif not line.startswith(("工作简历", "工作分工")):
                    pending_name = ""
                continue
            if not name or not duty:
                continue
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=evidence,
                parser=str(rule.get("parser", "S005_harbin_gov_detail_info_v1")),
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


def clean_current_duty_label(text: str) -> str:
    """清理领导信息字段中常见的职务标签。"""
    return re.sub(r"^\s*现任职务\s*[:：]\s*", "", compact_text(text))


def shandong_department_ldxx_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """山东省部门页领导信息解析器，按 #con-one-2 中的领导条目逐条抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or safe_select(soup, "#con-one-2, .ldxx_con") or [soup]
    rows: list[PersonRecord] = []
    for region in regions:
        cards = safe_select(region, str(rule.get("card_selector", ""))) or safe_select(region, "li")
        for card in cards:
            if not isinstance(card, Tag):
                continue
            name_node = card.select_one(str(rule.get("name_selector") or ".ldxx_name"))
            duty_node = card.select_one(str(rule.get("duty_selector") or ".ldxx_zw"))
            if not name_node or not duty_node:
                continue
            detail_node = card.select_one(str(rule.get("detail_link_selector") or "a[href]"))
            detail_url = ""
            if detail_node:
                href = str(detail_node.get("href", "")).strip()
                if href and not href.lower().startswith("javascript:"):
                    detail_url = urljoin(final_url or str(rule.get("url", "")), href)
            record = make_record(
                rule=rule,
                name=name_node.get_text(" ", strip=True),
                duty=clean_current_duty_label(duty_node.get_text(" ", strip=True)),
                evidence=card.get_text(" ", strip=True),
                parser=str(rule.get("parser", "S006_shandong_gov_ldxx_table_v1")),
                detail_url=detail_url,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


def shandong_government_leader_group_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """山东省政府领导页解析器，按职务分组绑定姓名链接。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    rows: list[PersonRecord] = []
    for region in regions:
        for group_node in safe_select(region, ".wip_ldcon"):
            if not isinstance(group_node, Tag):
                continue
            duty_node = group_node.select_one(".wip_ldconzw")
            if not duty_node:
                continue
            duty = compact_text(duty_node.get_text(" ", strip=True))
            for person_node in group_node.select(".wip_ldconryli"):
                link_nodes = [
                    node for node in person_node.select("a[href]")
                    if compact_text(node.get_text(" ", strip=True))
                ]
                if not link_nodes:
                    continue
                link_node = link_nodes[-1]
                record = make_record(
                    rule=rule,
                    name=link_node.get_text(" ", strip=True),
                    duty=duty,
                    evidence=f"{duty} {link_node.get_text(' ', strip=True)}",
                    parser=str(rule.get("parser", "S007_shandong_gov_leader_group_v1")),
                    detail_url=urljoin(final_url or str(rule.get("url", "")), str(link_node.get("href", ""))),
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
    return dedupe_records(rows)


def split_court_person_names(text: str) -> list[str]:
    """法院页面姓名拆分，保留姓名内部用于排版的空格。"""
    names: list[str] = []
    for part in re.split(r"[、，,／/|｜]+", str(text or "")):
        value = compact_text(part)
        if value:
            names.append(value)
    return names


def normalize_court_role(text: str) -> str:
    """清理法院页面职务中的排版空格。"""
    role = compact_text(text)
    role = re.sub(r"\s+", "", role)
    return role


def trim_embedded_court_role_header(text: str) -> str:
    """截去姓名串中误粘连的下一个法院职务标题。"""
    value = compact_text(text)
    match = COURT_INLINE_ROLE_HEADER_PATTERN.search(value)
    if match and match.start() > 0:
        return compact_text(value[:match.start()])
    return value


def collect_court_text_lines(region: Tag) -> list[str]:
    """提取法院正文完整文本行，避免嵌套 span 把同一行姓名拆碎。"""
    lines: list[str] = []
    seen: set[str] = set()

    def append_line(value: str) -> None:
        line = compact_text(value)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)

    for node in region.select("td, li, p"):
        if not isinstance(node, Tag):
            continue
        if node.select("td, li, p"):
            continue
        append_line(node.get_text("", strip=True))

    for value in region.get_text("\n", strip=True).splitlines():
        append_line(value)

    return lines


def iter_duty_name_line_parts(lines: list[str]) -> list[tuple[str, str, str]]:
    """从行文本中识别“职务：姓名”，兼容职务、冒号、姓名分三行的排版。"""
    results: list[tuple[str, str, str]] = []
    for index, line in enumerate(lines):
        clean_line = compact_text(line)
        if not clean_line or len(clean_line) > 180:
            continue
        if re.search(r"[:：]", clean_line):
            role_part, names_part = re.split(r"[:：]", clean_line, maxsplit=1)
            duty = compact_text(role_part).lstrip("　 ")
            evidence_text = clean_line
            if not names_part.strip() and index + 1 < len(lines):
                next_line = compact_text(lines[index + 1])
                if next_line and not re.search(r"[:：]", next_line):
                    names_part = next_line
                    evidence_text = f"{clean_line}{next_line}"
        else:
            if index + 2 >= len(lines):
                continue
            colon_line = compact_text(lines[index + 1])
            next_line = compact_text(lines[index + 2])
            if not re.fullmatch(r"[:：]", colon_line) or not next_line or re.search(r"[:：]", next_line):
                continue
            duty = clean_line.lstrip("　 ")
            names_part = next_line
            evidence_text = f"{duty}：{names_part}"
        if not duty or not names_part.strip():
            continue
        names_part = trim_embedded_court_role_header(names_part)
        if not names_part.strip():
            continue
        if not ROLE_WORD_PATTERN.search(duty):
            continue
        results.append((duty, names_part, evidence_text))
    return results


def court_text_duty_name_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """法院机构正文页解析器，抽取图片附近正文中的“职务：姓名”信息。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or safe_select(soup, ".txt_txt") or [soup]
    rows: list[PersonRecord] = []
    for region in regions:
        lines = collect_court_text_lines(region)
        for duty_part, names_part, evidence_text in iter_duty_name_line_parts(lines):
            duty = normalize_court_role(duty_part)
            for name in split_court_person_names(names_part):
                record = make_record(
                    rule=rule,
                    name=name,
                    duty=duty,
                    evidence=evidence_text,
                    parser=str(rule.get("parser", "S008_court_main_duty_name_text_v1")),
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
    return dedupe_records(rows)


def mct_leader_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """文化和旅游部页面解析器，兼容部领导卡片和正文“职务：姓名”。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []

    for card in safe_select(soup, ".bld_list"):
        if not isinstance(card, Tag):
            continue
        name_node = card.select_one(".bld_list_tit")
        duty_node = card.select_one(".bld_list_zw")
        if not name_node or not duty_node:
            continue
        link_node = card.select_one("a[href]")
        detail_url = ""
        if link_node:
            href = str(link_node.get("href", "")).strip()
            if href and not href.lower().startswith("javascript:"):
                detail_url = urljoin(final_url or str(rule.get("url", "")), href)
        record = make_record(
            rule=rule,
            name=name_node.get_text(" ", strip=True),
            duty=duty_node.get_text(" ", strip=True),
            evidence=card.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S009_mct_main_leader_group_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    text_regions = safe_select(soup, str(rule.get("leader_region_selector", "")))
    if not text_regions:
        text_regions = safe_select(soup, "#zoom, .TRS_Editor, .Custom_UnionStyle, .main_text, .article")
    if not text_regions:
        text_regions = [soup]

    for region in text_regions:
        lines = [compact_text(line) for line in region.get_text("\n", strip=True).splitlines()]
        lines = [line for line in lines if line]
        for duty, names_part, evidence_text in iter_duty_name_line_parts(lines):
            for name in split_person_names(names_part):
                record = make_record(
                    rule=rule,
                    name=name,
                    duty=duty,
                    evidence=evidence_text,
                    parser=str(rule.get("parser", "S009_mct_main_leader_group_v1")),
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
    return dedupe_records(rows)


def huhhot_leader_list_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """呼和浩特市政府信息公开页解析器，兼容部门领导列表和市政府首页首位领导块。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []

    for card in safe_select(soup, ".leaderList li"):
        if not isinstance(card, Tag):
            continue
        duty_nodes = card.select("p")
        if len(duty_nodes) < 2:
            continue
        duty_node = duty_nodes[0]
        name_node = duty_nodes[-1]
        link_node = card.select_one("a[href]")
        detail_url = ""
        if link_node:
            href = str(link_node.get("href", "")).strip()
            if href and not href.lower().startswith("javascript:"):
                detail_url = urljoin(final_url or str(rule.get("url", "")), href)
        record = make_record(
            rule=rule,
            name=name_node.get_text(" ", strip=True),
            duty=duty_node.get_text(" ", strip=True),
            evidence=card.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S010_huhhot_gov_xhr_leader_list_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    for leader_node in safe_select(soup, ".ldzc_block1_left p"):
        if not isinstance(leader_node, Tag):
            continue
        link_node = next(
            (node for node in leader_node.select("a[href]") if compact_text(node.get_text(" ", strip=True))),
            None,
        )
        duty_node = leader_node.select_one("span")
        if not link_node or not duty_node:
            continue
        name = link_node.get_text(" ", strip=True)
        href = str(link_node.get("href", "")).strip()
        detail_url = urljoin(final_url or str(rule.get("url", "")), href) if href else ""
        record = make_record(
            rule=rule,
            name=name,
            duty=duty_node.get_text(" ", strip=True),
            evidence=leader_node.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S010_huhhot_gov_xhr_leader_list_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    for card in safe_select(soup, ".ldzc_block1_right li"):
        if not isinstance(card, Tag):
            continue
        name_node = card.select_one("span")
        duty_node = card.select_one("p")
        link_node = card.select_one("a[href]")
        if not name_node or not duty_node:
            continue
        detail_url = ""
        if link_node:
            href = str(link_node.get("href", "")).strip()
            if href and not href.lower().startswith("javascript:"):
                detail_url = urljoin(final_url or str(rule.get("url", "")), href)
        record = make_record(
            rule=rule,
            name=name_node.get_text(" ", strip=True),
            duty=duty_node.get_text(" ", strip=True),
            evidence=card.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S010_huhhot_gov_xhr_leader_list_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    for leader_node in safe_select(soup, ".zwgk_block1_left .mid .mid_right span"):
        if not isinstance(leader_node, Tag):
            continue
        link_node = leader_node.select_one("a[href]")
        if not link_node:
            continue
        name = link_node.get_text(" ", strip=True)
        duty = compact_text(leader_node.get_text(" ", strip=True)).replace(name, "", 1)
        duty = compact_text(duty.strip("　 \u2003\xa0"))
        href = str(link_node.get("href", "")).strip()
        detail_url = urljoin(final_url or str(rule.get("url", "")), href) if href else ""
        record = make_record(
            rule=rule,
            name=name,
            duty=duty,
            evidence=leader_node.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S010_huhhot_gov_xhr_leader_list_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    return dedupe_records(rows)


def crop_text_by_anchors(text: str, content_scope: dict[str, Any]) -> str:
    """按内容锚点裁剪文本。"""
    result = str(text or "")
    start_anchor = str(content_scope.get("start_anchor", "") or "").strip()
    end_anchor = str(content_scope.get("end_anchor", "") or "").strip()
    if start_anchor and start_anchor in result:
        result = result.split(start_anchor, 1)[1]
    if end_anchor and end_anchor in result:
        result = result.split(end_anchor, 1)[0]
    return result


def apply_content_scope_to_region(region: Tag, content_scope: dict[str, Any]) -> str:
    """在外层区域内应用排除、纳入和文本锚点裁剪。"""
    for selector in content_scope.get("exclude_selectors", []) or []:
        for node in safe_select(region, str(selector)):
            if hasattr(node, "decompose"):
                node.decompose()

    include_selectors = [str(item).strip() for item in content_scope.get("include_selectors", []) or [] if str(item).strip()]
    if include_selectors:
        parts: list[str] = []
        for selector in include_selectors:
            for node in safe_select(region, selector):
                parts.append(node.get_text("\n", strip=True))
        text = "\n".join(parts)
    else:
        text = region.get_text("\n", strip=True)
    return crop_text_by_anchors(text, content_scope)


def get_region_text(rule: dict[str, Any], html: str) -> str:
    """按明确领导区域选择器取得正文文本；选择器失效时退回整页文本。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = safe_select(soup, str(rule.get("leader_region_selector", ""))) or [soup]
    content_scope = rule.get("content_scope")
    if not isinstance(content_scope, dict):
        content_scope = {}
    return "\n".join(apply_content_scope_to_region(region, content_scope) for region in regions)


def split_person_names(text: str) -> list[str]:
    """拆分同一职务后的多个姓名。"""
    names: list[str] = []
    for part in re.split(r"[、，,／/|｜\s　]+", str(text or "")):
        value = part.strip()
        if value:
            names.append(value)
    return names


def split_public_person_names(text: str) -> list[str]:
    """拆分政务公开名单中的姓名，兼容用间隔号连接的多人姓名。"""
    raw_text = compact_text(text)
    raw_text = strip_person_name_annotation(raw_text)
    if re.fullmatch(r"[一-鿿]{2,6}·[一-鿿]{2,6}", raw_text):
        return [raw_text]
    parts = re.split(r"[、，,／/|｜\s　]+", raw_text)
    names: list[str] = []
    index = 0
    while index < len(parts):
        part = strip_person_name_annotation(str(parts[index] or "").strip())
        if not part:
            index += 1
            continue
        if re.fullmatch(r"[一-鿿·]{2,12}", part):
            names.append(part)
            index += 1
            continue
        if re.fullmatch(r"[一-鿿]", part) and index + 1 < len(parts):
            next_part = str(parts[index + 1] or "").strip()
            if re.fullmatch(r"[一-鿿]", next_part):
                names.append(part + next_part)
                index += 2
                continue
        index += 1
    return names


def strip_person_name_annotation(text: str) -> str:
    """去掉姓名后的短括号备注，如“包永贵（援青）”。"""
    value = compact_text(text)
    return re.sub(r"[（(][^（）()]{1,20}[）)]$", "", value).strip()


def normalize_spaced_role(text: str) -> str:
    """清理职务中用于排版的空格，如“副 市 长”“会 长”。"""
    return re.sub(r"(?<=[一-鿿])[\s　\xa0]+(?=[一-鿿])", "", compact_text(text))


def split_name_duty_sequence(text: str) -> list[tuple[str, str, str]]:
    """解析“姓名 职务 姓名 职务”连续结构。"""
    tokens = [compact_text(item) for item in re.split(r"\s+", str(text or "")) if compact_text(item)]
    rows: list[tuple[str, str, str]] = []

    def read_name(start: int) -> tuple[str, int]:
        if start >= len(tokens):
            return "", 0
        token = tokens[start]
        if ROLE_WORD_PATTERN.search(normalize_spaced_role(token)):
            return "", 0
        if re.search(r"日报|网站|学院|频道|首页|政府网|人物库|纠错|来源", token):
            return "", 0
        if re.fullmatch(r"[一-鿿·]{2,12}", token):
            return token, 1
        if re.fullmatch(r"[一-鿿]", token) and start + 1 < len(tokens):
            next_token = tokens[start + 1]
            if re.fullmatch(r"[一-鿿]", next_token):
                return token + next_token, 2
        return "", 0

    index = 0
    while index + 1 < len(tokens):
        name, name_size = read_name(index)
        if not name:
            index += 1
            continue
        duty_parts: list[str] = []
        next_index = index + name_size
        while next_index < len(tokens):
            next_token = tokens[next_index]
            next_name, next_name_size = read_name(next_index)
            following_index = next_index + next_name_size
            following = tokens[following_index] if following_index < len(tokens) else ""
            if duty_parts and next_name and ROLE_WORD_PATTERN.search(normalize_spaced_role(following)):
                break
            duty_parts.append(next_token)
            next_index += 1
        duty = normalize_spaced_role(" ".join(duty_parts))
        if duty and ROLE_WORD_PATTERN.search(duty):
            rows.append((name, duty, f"{name} {duty}"))
        index = max(next_index, index + 1)
    return rows


CE_DISTRICT_ROLE_WORDS = (
    "副书记",
    "副省长",
    "副市长",
    "副主席",
    "副主任",
    "副秘书长",
    "书记",
    "省长",
    "市长",
    "主席",
    "主任",
    "秘书长",
)


CE_DISTRICT_ROLE_PREFIX = re.compile(
    rf"(?P<role>{'|'.join(CE_DISTRICT_ROLE_WORDS)})\s*"
    rf"(?P<name>[一-鿿·]{{2,20}}?)(?:同志)?(?:简历)?"
    rf"(?=(?:{'|'.join(CE_DISTRICT_ROLE_WORDS)})|\s|$|[（(\[])"
)


def append_ce_district_role_prefix_records(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    text: str,
    parser: str,
    snapshot_path: Path | None,
    detail_url: str = "",
) -> None:
    """追加中国经济网“职务+姓名”记录，兼容带间隔点的长姓名。"""
    for match in CE_DISTRICT_ROLE_PREFIX.finditer(compact_text(text)):
        duty = normalize_spaced_role(match.group("role"))
        record = make_record(
            rule=rule,
            name=match.group("name"),
            duty=duty,
            evidence=match.group(0),
            parser=parser,
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)


def append_ce_district_link_records(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    region: Tag,
    final_url: str,
    parser: str,
    snapshot_path: Path | None,
) -> None:
    """优先从当前名单区块的详情链接抽取，遇到任免动态即停止。"""
    base_url = final_url or str(rule.get("url", ""))
    block_nodes = region.find_all(["p", "li", "tr"], recursive=True)
    if not block_nodes:
        return

    for block in block_nodes:
        block_text = compact_text(block.get_text(" ", strip=True))
        if not block_text:
            continue
        if re.search(r"任免动态|延伸阅读|相关新闻|各地市领导", block_text):
            break

        link_nodes = [node for node in block.find_all("a", href=True) if isinstance(node, Tag)]
        if not link_nodes:
            append_ce_district_role_prefix_records(
                rows=rows,
                rule=rule,
                text=block_text,
                parser=parser,
                snapshot_path=snapshot_path,
            )
            continue

        for link_node in link_nodes:
            link_text = compact_text(link_node.get_text(" ", strip=True))
            if not link_text:
                continue
            detail_url = urljoin(base_url, str(link_node.get("href", "")).strip())
            append_ce_district_role_prefix_records(
                rows=rows,
                rule=rule,
                text=link_text,
                parser=parser,
                snapshot_path=snapshot_path,
                detail_url=detail_url,
            )


def append_duty_colon_records(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    text: str,
    parser: str,
    snapshot_path: Path | None,
) -> None:
    """从“职务：姓名”文本中追加记录，兼容职务中的排版空格。"""
    role_words = (
        r"书\s*记|主\s*席|主\s*任|局\s*长|厅\s*长|部\s*长|院\s*长|秘\s*书\s*长|"
        r"委\s*员|负责人|法定代表人|组\s*长|省\s*长|市\s*长|馆\s*长|所\s*长|"
        r"站\s*长|队\s*长|社\s*长|校\s*长|处\s*长|科\s*长|会\s*长|团\s*长|"
        r"台\s*长|庭\s*长|干部|职员|专员|巡视员|督察专员|总经理|董事长|监事长|"
        r"总编辑|总工程师|总会计师|总经济师"
    )
    role_colon = re.compile(
        rf"(?P<role>[^。；;\n：:]{{0,70}}?(?:{role_words})[^。；;\n：:]{{0,40}}?)\s*[:：]\s*"
        rf"(?P<names>[^。；;\n]{{2,120}}?)"
        rf"(?=(?:[^。；;\n：:]{{0,70}}?(?:{role_words})[^。；;\n：:]{{0,40}}?\s*[:：])|[。；;\n]|$)"
    )
    for match in role_colon.finditer(text):
        duty = normalize_spaced_role(match.group("role"))
        if not ROLE_WORD_PATTERN.search(duty):
            continue
        for name in split_public_person_names(match.group("names")):
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=match.group(0),
                parser=parser,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    lines = [compact_text(line) for line in text.splitlines() if compact_text(line)]
    for index, line in enumerate(lines):
        duty = ""
        names_part = ""
        evidence_text = line
        if re.search(r"[:：]", line):
            role_part, names_part = re.split(r"[:：]", line, maxsplit=1)
            duty = normalize_spaced_role(role_part)
            if not names_part.strip() and index + 1 < len(lines):
                names_part = lines[index + 1]
                evidence_text = f"{line}{names_part}"
        else:
            candidate_role = normalize_spaced_role(line)
            if not ROLE_WORD_PATTERN.search(candidate_role) or index + 1 >= len(lines):
                continue
            next_line = compact_text(lines[index + 1])
            if re.fullmatch(r"[:：]", next_line) and index + 2 < len(lines):
                duty = candidate_role
                names_part = lines[index + 2]
                evidence_text = f"{line}：{names_part}"
            elif re.match(r"^[:：]\s*.+", next_line):
                duty = candidate_role
                names_part = re.sub(r"^[:：]\s*", "", next_line)
                evidence_text = f"{line}{next_line}"
        if not duty or not names_part or not ROLE_WORD_PATTERN.search(duty):
            continue
        for name in split_public_person_names(names_part):
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=evidence_text,
                parser=parser,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)


def public_zhengzhou_leader_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """郑州市政务公开领导列表解析器，列表缺职务时读取个人详情页简介。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    base_url = final_url or str(rule.get("url", ""))
    for node in safe_select(soup, ".content-leader-name, .content-title"):
        text = node.get_text(" ", strip=True)
        for name, duty, evidence in split_name_duty_sequence(text):
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=evidence,
                parser=str(rule.get("parser", "S011_zhengzhou_public_leader_list_v1")),
                detail_url=base_url,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    for link_node in safe_select(soup, ".common-box .page-list a[href], .common-box .leader-list a[href], .common-box a[href]"):
        if not isinstance(link_node, Tag):
            continue
        name_node = link_node.select_one("span")
        duty_node = link_node.select_one("b")
        name = name_node.get_text(" ", strip=True) if name_node else link_node.get_text(" ", strip=True)
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        href = str(link_node.get("href", "")).strip()
        detail_url = urljoin(base_url, href) if href else ""
        if not duty and detail_url:
            duty = extract_zhengzhou_detail_duty(detail_url, name)
        if not duty:
            page_text = compact_text((soup.select_one(".common-box") or soup).get_text(" ", strip=True))
            duty = "市政府领导" if "市政府领导" in page_text else "机构领导"
        record = make_record(
            rule=rule,
            name=name,
            duty=duty,
            evidence=link_node.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S011_zhengzhou_public_leader_list_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    return dedupe_records(rows)


def extract_zhengzhou_detail_duty(detail_url: str, name: str) -> str:
    """读取郑州个人详情页，从简介中的“现任”句提取职务。"""
    try:
        from urllib.request import Request, urlopen

        request = Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            detail_html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one(".main-body") or soup.select_one(".body-wrap") or soup
    text = region.get_text("\n", strip=True)
    match = re.search(r"现任(?P<duty>[^。；;\n]{3,180})", text)
    if match:
        return compact_text(match.group("duty"))
    match = re.search(r"(?:职务|职位)\s*[:：]\s*(?P<duty>[^。；;\n]{3,120})", text)
    if match:
        return compact_text(match.group("duty"))
    compact_region_text = compact_text(text)
    display_name = compact_text(name)
    compact_names = []
    no_space_name = re.sub(r"[\s　\xa0]+", "", display_name)
    if no_space_name != display_name:
        compact_names.append(no_space_name)
    compact_names.append(display_name)
    for current_name in compact_names:
        name_positions = [match.start() for match in re.finditer(re.escape(current_name), compact_region_text)]
        for current, next_position in zip(name_positions, name_positions[1:]):
            duty = compact_text(compact_region_text[current + len(current_name):next_position])
            duty = duty.strip("，,：: ")
            if 2 < len(duty) <= 180 and ROLE_WORD_PATTERN.search(normalize_spaced_role(duty[:80])):
                return duty
        last_index = compact_region_text.rfind(current_name)
        if last_index >= 0:
            duty = compact_text(compact_region_text[last_index + len(current_name):])
            duty = re.split(r"[。；;]", duty, maxsplit=1)[0]
            if ROLE_WORD_PATTERN.search(normalize_spaced_role(duty[:80])):
                return duty
    name_match = re.search(rf"{re.escape(display_name)}\s*[，,]\s*(?P<duty>[^。；;\n]{{3,180}})", text)
    if name_match:
        duty = compact_text(name_match.group("duty"))
        if ROLE_WORD_PATTERN.search(normalize_spaced_role(duty[:80])):
            return duty
    lines = [compact_text(line) for line in text.splitlines() if compact_text(line)]
    normalized_name = re.sub(r"[\s　\xa0]+", "", compact_text(name))
    for index, line in enumerate(lines[:-1]):
        if re.sub(r"[\s　\xa0]+", "", line) != normalized_name:
            continue
        for duty_line in lines[index + 1:index + 4]:
            duty = compact_text(duty_line)
            if ROLE_WORD_PATTERN.search(normalize_spaced_role(duty)):
                return duty
    return ""


def qingdao_government_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """青岛政务网机构信息页解析器，兼容领导表格和市政府领导分组。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    for table in safe_select(soup, "table#table5"):
        table_text = compact_text(table.get_text(" ", strip=True))
        if "职务" not in table_text or "个人简历" not in table_text:
            continue
        for row in table.select("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < 3:
                continue
            label = compact_text(cells[1].get_text(" ", strip=True))
            if normalize_spaced_role(label) != "职务":
                continue
            name = cells[0].get_text(" ", strip=True)
            duty = cells[2].get_text(" ", strip=True)
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=row.get_text(" ", strip=True),
                parser=str(rule.get("parser", "S012_qingdao_gov_ldxx_table_v1")),
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)

    for region in safe_select(soup, "#dw_dq .ldleft, .ldleft"):
        text = region.get_text("\n", strip=True)
        text = re.sub(r"^市政府领导\s*", "", compact_text(text))
        pattern = re.compile(
            r"(?P<role>市\s*长|副\s*市\s*长|秘\s*书\s*长|副秘书长)\s*[:：]\s*"
            r"(?P<names>.*?)(?=(?:市\s*长|副\s*市\s*长|秘\s*书\s*长|副秘书长)\s*[:：]|$)"
        )
        for match in pattern.finditer(text):
            duty = normalize_spaced_role(match.group("role"))
            for name in split_public_person_names(match.group("names")):
                record = make_record(
                    rule=rule,
                    name=name,
                    duty=duty,
                    evidence=match.group(0),
                    parser=str(rule.get("parser", "S012_qingdao_gov_ldxx_table_v1")),
                    snapshot_path=snapshot_path,
                    apply_weak_wordlist=False,
                )
                if record:
                    rows.append(record)
    return dedupe_records(rows)


def ce_district_leader_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """中国经济网地方党政人物库解析器，裁掉任免动态后抽取当前领导名单。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    parser = str(rule.get("parser", "S013_ce_district_leader_list_v1"))
    regions = safe_select(soup, ".main .ren2, .main .TRS_Editor, .content .TRS_Editor, .trs_editor_view")
    if not regions:
        regions = safe_select(soup, ".main, .content")
    for region in regions:
        before_link_count = len(rows)
        if isinstance(region, Tag):
            append_ce_district_link_records(rows, rule, region, final_url, parser, snapshot_path)
        if len(rows) > before_link_count:
            continue

        text = region.get_text("\n", strip=True)
        has_current_article_list = "任免动态" in text
        text = re.split(r"任免动态|延伸阅读|相关新闻|各地市领导", text, maxsplit=1)[0]
        if re.search(r"党中央|国务院部门|关于经济日报社|版权声明", text):
            continue
        if has_current_article_list:
            append_ce_district_role_prefix_records(rows, rule, text, parser, snapshot_path)
            continue
        before_count = len(rows)
        for name, duty, evidence in split_name_duty_sequence(text):
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=evidence,
                parser=parser,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
        if len(rows) > before_count:
            continue
        append_ce_district_role_prefix_records(rows, rule, text, parser, snapshot_path)
    return dedupe_records(rows)


def ce_city_four_leaders_table_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """中国经济网地市四套班子一把手表格解析器。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    base_url = final_url or str(rule.get("url", ""))
    parser = str(rule.get("parser", "S014_ce_district_city_four_leaders_table_v1"))
    regions = safe_select(soup, ".content .TRS_Editor, .trs_editor_view, #articleText, .content") or [soup]
    for region in regions:
        for table in safe_select(region, "table"):
            table_rows = table.select("tr")
            header_cells: list[Tag] = []
            data_start_index = 0
            for row_index, table_row in enumerate(table_rows):
                cells = [cell for cell in table_row.find_all(["td", "th"], recursive=False) if isinstance(cell, Tag)]
                header_text = compact_text(" ".join(cell.get_text(" ", strip=True) for cell in cells))
                if len(cells) >= 4 and re.search(r"各市|各地|州市", header_text) and re.search(r"书记", header_text):
                    header_cells = cells
                    data_start_index = row_index + 1
                    break
            if not header_cells:
                continue
            roles = [normalize_ce_city_table_role(cell.get_text(" ", strip=True)) for cell in header_cells]
            for table_row in table_rows[data_start_index:]:
                cells = [cell for cell in table_row.find_all(["td", "th"], recursive=False) if isinstance(cell, Tag)]
                if len(cells) < 2:
                    continue
                city = compact_text(cells[0].get_text(" ", strip=True))
                if not city or re.search(r"各市|书记|人大|市长|政协|纠错|邮箱", city):
                    continue
                for column_index in range(1, min(len(cells), len(roles))):
                    role = roles[column_index]
                    if not role:
                        continue
                    name, detail_url, evidence = extract_ce_city_table_person(cells[column_index], base_url)
                    if not name:
                        continue
                    record = make_record(
                        rule=rule,
                        name=name,
                        duty=build_ce_city_table_duty(city, role),
                        evidence=evidence,
                        parser=parser,
                        detail_url=detail_url,
                        snapshot_path=snapshot_path,
                        apply_weak_wordlist=False,
                    )
                    if record:
                        rows.append(record)
    return dedupe_records(rows)


def normalize_ce_city_table_role(text: str) -> str:
    """标准化地市四套班子表头职务。"""
    value = normalize_spaced_role(text)
    if "书记" in value:
        return "党委书记"
    if "人大" in value and "主任" in value:
        return "人大常委会主任"
    if "市长" in value or "州长" in value:
        return "政府主要负责人"
    if "政协" in value and "主席" in value:
        return "政协主席"
    return ""


def build_ce_city_table_duty(city: str, role: str) -> str:
    """结合地名生成更准确的职务文本。"""
    place = compact_text(city)
    if role == "党委书记":
        if place.endswith(("市", "州", "盟")):
            return f"{place}委书记"
        if place.endswith("地区"):
            return f"{place}地委书记"
        return f"{place}党委书记"
    if role == "政府主要负责人":
        if place.endswith(("市", "州")):
            return f"{place}长"
        return f"{place}政府主要负责人"
    return f"{place}{role}"


def extract_ce_city_table_person(cell: Tag, base_url: str) -> tuple[str, str, str]:
    """从表格单元格读取当前人员姓名和详情链接。"""
    evidence = compact_text(cell.get_text(" ", strip=True))
    for link_node in cell.find_all("a", href=True):
        if not isinstance(link_node, Tag):
            continue
        link_text = compact_text(link_node.get_text(" ", strip=True))
        name = clean_ce_city_table_name(link_text)
        if name:
            return name, urljoin(base_url, str(link_node.get("href", "")).strip()), evidence
    return clean_ce_city_table_name(evidence), "", evidence


def clean_ce_city_table_name(text: str) -> str:
    """清理表格姓名中的兼任、代理等附注。"""
    value = compact_text(text)
    value = re.sub(r"[（(][^）)]*[）)]", "", value)
    value = re.sub(r"(?:兼|代|暂缺|空缺|待补)$", "", value)
    value = re.sub(r"[^一-鿿·]", "", value)
    if not re.fullmatch(r"[一-鿿·]{2,12}", value):
        return ""
    if ROLE_WORD_PATTERN.search(value):
        return ""
    return value


def moj_leader_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """司法部机构页解析器，兼容部领导卡片和厅局/直属单位领导字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    base_url = final_url or str(rule.get("url", ""))
    for card in safe_select(soup, ".leadList"):
        name_node = card.select_one(".tt .nm")
        duty_node = card.select_one(".tt em")
        if not name_node or not duty_node:
            continue
        link_node = card.select_one(".tt a[href], a[href]")
        detail_url = urljoin(base_url, str(link_node.get("href", ""))) if link_node else ""
        record = make_record(
            rule=rule,
            name=name_node.get_text(" ", strip=True),
            duty=duty_node.get_text(" ", strip=True),
            evidence=card.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S015_moj_main_leader_list_v1")),
            detail_url=detail_url,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    for region in safe_select(soup, ".left_list, .TRS_Editor"):
        text = region.get_text("\n", strip=True)
        text = re.split(r"联系方式|办公地址|联系电话|新闻动态", text, maxsplit=1)[0]
        append_duty_colon_records(rows, rule, text, str(rule.get("parser", "S015_moj_main_leader_list_v1")), snapshot_path)
    return dedupe_records(rows)


def neac_leader_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """国家民委机构页解析器，兼容委领导卡片和部门领导字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    base_url = final_url or str(rule.get("url", ""))
    for card in safe_select(soup, ".w1-3 li a[href]"):
        name_node = card.select_one("b")
        duty_node = card.select_one("span")
        if not name_node or not duty_node:
            continue
        record = make_record(
            rule=rule,
            name=name_node.get_text(" ", strip=True),
            duty=duty_node.get_text(" ", strip=True),
            evidence=card.get_text(" ", strip=True),
            parser=str(rule.get("parser", "S016_neac_main_leader_card_v1")),
            detail_url=urljoin(base_url, str(card.get("href", ""))),
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    for region in safe_select(soup, ".p3"):
        text = region.get_text("\n", strip=True)
        text = re.split(r"联系方式|工作职责|主要职责", text, maxsplit=1)[0]
        append_duty_colon_records(rows, rule, text, str(rule.get("parser", "S016_neac_main_leader_card_v1")), snapshot_path)
    append_neac_society_records(rows, rule, soup, snapshot_path)
    return dedupe_records(rows)


def neac_society_org_people_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """国家民委主管社团“机构人员设置”专用解析器。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    append_neac_society_records(rows, rule, soup, snapshot_path)
    return dedupe_records(rows)


def append_neac_society_records(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    soup: BeautifulSoup,
    snapshot_path: Path | None,
) -> None:
    """抽取国家民委主管社团“机构人员设置”中的会长、副会长、秘书长名单。"""
    parser_name = str(rule.get("parser", "S016_neac_main_leader_card_v1"))
    for region in safe_select(soup, ".mz_list"):
        lines = extract_neac_society_lines(region)
        current_role = ""
        index = 0
        while index < len(lines):
            role, role_size = read_neac_society_role_header(lines, index)
            if role:
                current_role = role
                index += role_size
                continue
            if not current_role:
                index += 1
                continue

            parsed_name, adjunct_duty, evidence, consumed = read_neac_society_person(lines, index)
            if not parsed_name:
                index += 1
                continue
            duty = combine_neac_society_duty(current_role, adjunct_duty)
            record = make_record(
                rule=rule,
                name=parsed_name,
                duty=duty,
                evidence=f"{current_role} {evidence}",
                parser=parser_name,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
            index += consumed


def extract_neac_society_lines(region: Tag) -> list[str]:
    """按页面块提取社团人员设置行，兼容 span 嵌套和换行碎片。"""
    content_region = region.select_one(".content .pd15, .pd15") or region
    block_nodes = content_region.find_all(["p", "div"], recursive=True)
    lines: list[str] = []
    for node in block_nodes:
        if not isinstance(node, Tag):
            continue
        if node.find(["p", "div"]):
            continue
        text = compact_text(node.get_text(" ", strip=True))
        if text:
            lines.append(text)
    for node in content_region.find_all("div", recursive=True):
        if not isinstance(node, Tag):
            continue
        direct_span_texts = [
            compact_text(span.get_text(" ", strip=True))
            for span in node.find_all("span", recursive=False)
            if compact_text(span.get_text(" ", strip=True))
        ]
        if direct_span_texts:
            line = compact_text(" ".join(direct_span_texts))
            if line and line not in lines:
                lines.append(line)
    if not lines:
        lines = [line.strip() for line in region.get_text("\n", strip=True).splitlines() if line.strip()]
    return lines


def read_neac_society_role_header(lines: list[str], index: int) -> tuple[str, int]:
    """识别国家民委社团页的职务标题，兼容“副会长（/11人）：”拆行。"""
    line = compact_text(lines[index])
    candidates: list[tuple[str, int]] = []
    if is_neac_society_bare_role_header(line) and not re.search(r"[:：]", line):
        buffer = line
        for size in range(2, 4):
            if index + size - 1 >= len(lines):
                break
            buffer += compact_text(lines[index + size - 1])
            if re.search(r"[:：]", buffer):
                candidates.append((buffer, size))
                break
    if index + 1 < len(lines):
        next_line = compact_text(lines[index + 1])
        if is_neac_society_bare_role_header(line) and (
            re.fullmatch(r"[:：]", next_line) or re.search(r"[（(]\s*$", line)
        ):
            candidates.append((line + next_line, 2))
    if re.search(r"[:：]", line):
        candidates.append((line, 1))
    if is_neac_society_bare_role_header(line):
        candidates.append((line, 1))

    for candidate, consumed in candidates:
        role = normalize_neac_society_role(candidate)
        if role:
            return role, consumed
    return "", 0


def is_neac_society_bare_role_header(text: str) -> bool:
    """判断没有冒号时是否仍像纯职务标题，避免把人员职称误作分组。"""
    value = normalize_spaced_role(text).strip()
    value = re.sub(r"[（(]\s*\d+\s*人\s*[）)]", "", value)
    value = re.sub(r"[（(]\s*按[^）)]*排序\s*[）)]", "", value)
    value = re.sub(r"[（(]\s*$", "", value)
    value = value.strip("：:，,、；; ")
    if not value or len(value) > 20:
        return False
    if re.search(r"大学|学院|研究|民族|民委|学校|中心|公司|委员会|协会|办公厅|司|局|院士|教授|退休", value):
        return False
    return bool(
        re.fullmatch(
            r"(?:常务)?(?:副)?会长|(?:常务)?(?:副)?理事长|(?:副)?秘书长|法定代表人|"
            r"会长、法定代表人|秘书长、法定代表人",
            value,
        )
    )


def normalize_neac_society_role(text: str) -> str:
    """标准化社团页职务标题，去掉人数说明。"""
    value = normalize_spaced_role(text)
    role_part = re.split(r"[:：]", value, maxsplit=1)[0]
    role_part = re.sub(r"[（(]\s*\d+\s*人\s*[）)]", "", role_part)
    role_part = re.sub(r"[（(]\s*$", "", role_part)
    role_part = role_part.strip("：:，,、；; ")
    if not role_part or len(role_part) > 40:
        return ""
    role_part = re.sub(r"[（(]\s*按[^）)]*排序\s*[）)]", "", role_part).strip()
    if role_part.count("（") != role_part.count("）") or role_part.count("(") != role_part.count(")"):
        return ""
    if re.search(r"[）)]$", role_part) and not re.search(r"[（(]", role_part):
        return ""
    if re.fullmatch(r"[（(].+[）)]", role_part):
        return ""
    if not re.search(r"会长|理事长|秘书长|法定代表人", role_part):
        return ""
    return role_part


def read_neac_society_person(lines: list[str], index: int) -> tuple[str, str, str, int]:
    """读取社团页单个人员行，返回姓名、姓名后的附加职务、证据和消耗行数。"""
    first_line = lines[index]
    first_value = re.sub(r"[\s\u2002\u3000\xa0]+", "", compact_text(first_line))
    if (
        re.fullmatch(r"[一-鿿]", first_value)
        and index + 1 < len(lines)
        and re.fullmatch(r"[一-鿿]", compact_text(lines[index + 1]))
    ):
        name = first_value + compact_text(lines[index + 1])
        tail = ""
        consumed = 2
    else:
        name, tail = split_neac_society_name_tail(first_line)
        consumed = 1
    if not name:
        return "", "", "", 1

    while index + consumed < len(lines):
        next_line = lines[index + consumed]
        if is_neac_ethnic_name_continuation(next_line):
            name = name + re.sub(r"[\s\u2002\u3000\xa0]+", "", compact_text(next_line))
            consumed += 1
            continue
        if len(name) == 1 and re.fullmatch(r"[一-鿿]", compact_text(next_line)):
            name += compact_text(next_line)
            consumed += 1
            continue
        break

    duty_parts = [tail] if tail else []
    while index + consumed < len(lines):
        next_line = lines[index + consumed]
        if read_neac_society_role_header(lines, index + consumed)[0]:
            break
        if is_neac_society_person_entry_start(lines, index + consumed):
            break
        duty_parts.append(compact_text(next_line))
        consumed += 1

    adjunct_duty = normalize_spaced_role("".join(duty_parts))
    evidence = " ".join(compact_text(lines[item]) for item in range(index, index + consumed))
    return name, adjunct_duty, evidence, max(consumed, 1)


def split_neac_society_name_tail(line: str) -> tuple[str, str]:
    """拆出社团页人员行开头姓名和后续单位职称。"""
    parts = [compact_text(part) for part in re.split(r"[\u2002\u3000\xa0 ]{2,}", line) if compact_text(part)]
    if parts:
        first = re.sub(r"[\s\u2002\u3000\xa0]+", "", parts[0])
        if len(parts) >= 2 and re.fullmatch(r"[一-鿿]", first) and re.fullmatch(r"[一-鿿]", compact_text(parts[1])):
            name = first + compact_text(parts[1])
            return name, compact_text("".join(parts[2:]))
        if is_neac_society_person_start(first):
            name = first
            tail = "".join(parts[1:])
            return name, compact_text(tail)

    loose_parts = [compact_text(part) for part in re.split(r"[\u2002\u3000\xa0 ]+", line) if compact_text(part)]
    if len(loose_parts) >= 2:
        first = re.sub(r"[\s\u2002\u3000\xa0]+", "", loose_parts[0])
        second = re.sub(r"[\s\u2002\u3000\xa0]+", "", loose_parts[1])
        if re.fullmatch(r"[一-鿿]{2,8}", first) and re.fullmatch(r"·[一-鿿]{1,8}", second):
            name = first + second
            return name, compact_text("".join(loose_parts[2:]))
        if re.fullmatch(r"[一-鿿]", first) and re.fullmatch(r"[一-鿿]", second):
            name = first + second
            return name, compact_text("".join(loose_parts[2:]))
        if is_neac_society_person_start(first):
            return first, compact_text("".join(loose_parts[1:]))

    compact_line = compact_text(line)
    parenthetical_match = re.fullmatch(r"(?P<name>[一-鿿·]{2,12})[（(](?P<tail>[^）)]+)[）)]", compact_line)
    if parenthetical_match and is_neac_society_person_start(parenthetical_match.group("name")):
        return parenthetical_match.group("name"), parenthetical_match.group("tail")
    if is_neac_society_person_start(compact_line):
        return re.sub(r"[\s\u2002\u3000\xa0]+", "", compact_line), ""
    return "", ""


def is_neac_ethnic_name_continuation(line: str) -> bool:
    """判断“·阿热孜”这类少数民族姓名后半段。"""
    value = re.sub(r"[\s\u2002\u3000\xa0]+", "", compact_text(line))
    return bool(re.fullmatch(r"·[一-鿿]{1,8}", value))


def is_neac_society_person_entry_start(lines: list[str], index: int) -> bool:
    """结合下一行判断当前位置是否为新人员起点。"""
    if index >= len(lines):
        return False
    value = re.sub(r"[\s\u2002\u3000\xa0]+", "", compact_text(lines[index]))
    if (
        re.fullmatch(r"[一-鿿]", value)
        and index + 1 < len(lines)
        and re.fullmatch(r"[一-鿿]", compact_text(lines[index + 1]))
    ):
        return True
    name, _ = split_neac_society_name_tail(lines[index])
    return bool(name)


def is_neac_society_person_start(line: str) -> bool:
    """判断一行是否更像新的人名，而不是单位、学历或职称片段。"""
    value = re.sub(r"[\s\u2002\u3000\xa0]+", "", compact_text(line))
    if not re.fullmatch(r"[一-鿿·]{1,12}", value):
        return False
    if len(value) == 1:
        return False
    if ROLE_WORD_PATTERN.search(value):
        return False
    non_name_hints = (
        "大学", "学院", "研究", "民族", "民委", "学校", "附中", "中心", "出版社",
        "委员会", "协会", "科学院", "政策", "教育", "办公室", "博物馆", "外国语",
    )
    if any(hint in value for hint in non_name_hints):
        return False
    return True


def get_moe_previous_section_title(region: Tag) -> str:
    """读取教育部司局页正文块前一个栏目标题。"""
    start_node: Tag = region
    if isinstance(region.parent, Tag):
        start_node = region.parent
    for sibling in start_node.previous_siblings:
        if not isinstance(sibling, Tag):
            continue
        title = compact_text(sibling.get_text(" ", strip=True))
        if title:
            return title
    return ""


def is_moe_leader_region(region: Tag) -> bool:
    """教育部司局页领导信息通常位于“司领导/局领导/组领导”栏目下。"""
    title = get_moe_previous_section_title(region)
    if not title:
        return False
    if "领导" not in title:
        return False
    return not re.search(r"内设|机构设置|介绍|职能|职责|联系方式|地址", title)


def combine_neac_society_duty(role: str, adjunct_duty: str) -> str:
    """社团页中“会长/副会长”和姓名后的单位职称都作为职务信息保留。"""
    main_role = normalize_neac_society_role(role) or normalize_spaced_role(role)
    adjunct = compact_text(adjunct_duty)
    if adjunct:
        return f"{main_role}；{adjunct}"
    return main_role


def moe_leader_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """教育部机构页解析器，兼容部领导、司局领导和驻部纪检监察组。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[PersonRecord] = []
    parser_name = str(rule.get("parser", "S018_moe_main_department_leader_v1"))
    for item in safe_select(soup, "ul#list li"):
        text = compact_text(item.get_text(" ", strip=True))
        match = re.match(r"(?P<name>[一-鿿·\s　]{2,12})\s*[:：]\s*(?P<duty>.+)$", text)
        if not match:
            continue
        record = make_record(
            rule=rule,
            name=match.group("name"),
            duty=match.group("duty"),
            evidence=text,
            parser=parser_name,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)

    for region in safe_select(soup, "#siju-section .TRS_Editor, .section-jijianzu .TRS_Editor"):
        if isinstance(region, Tag) and not is_moe_leader_region(region):
            continue
        text = region.get_text("\n", strip=True)
        for name, duty, evidence in split_name_duty_sequence(text):
            record = make_record(
                rule=rule,
                name=name,
                duty=duty,
                evidence=evidence,
                parser=parser_name,
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
        append_duty_colon_records(rows, rule, text, parser_name, snapshot_path)
    return dedupe_records(rows)


def duty_colon_name_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """职务冒号姓名型解析器，如“党委书记、副馆长：陈樱”；半结构不依赖词表。"""
    text = get_region_text(rule, html)
    rows: list[PersonRecord] = []
    role_colon = re.compile(
        r"(?P<role>[^。；;\n]{1,60}?(?:书记|主席|主任|局长|厅长|部长|院长|秘书长|委员|负责人|法定代表人|"
        r"省长|市长|馆长|所长|站长|队长|社长|校长|处长|科长|会长|团长|台长|庭长|干部|专员|巡视员|"
        r"督察专员|总经理|董事长|监事长|总编辑|总工程师|总会计师|总经济师))"
        r"\s*[:：]\s*(?P<names>[^。；;\n]{2,120})"
    )
    for match in role_colon.finditer(text):
        duty = compact_text(match.group("role"))
        for part in split_person_names(match.group("names")):
            record = make_record(
                rule=rule,
                name=part,
                duty=duty,
                evidence=match.group(0),
                parser=str(rule.get("parser", "V005_text_duty_colon_name_v1")),
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    lines = [compact_text(line) for line in re.split(r"[\r\n]+", text)]
    lines = [line for line in lines if line]
    for duty, names_part, evidence_text in iter_duty_name_line_parts(lines):
        for part in split_person_names(names_part):
            record = make_record(
                rule=rule,
                name=part,
                duty=duty,
                evidence=evidence_text,
                parser=str(rule.get("parser", "V005_text_duty_colon_name_v1")),
                snapshot_path=snapshot_path,
                apply_weak_wordlist=False,
            )
            if record:
                rows.append(record)
    return dedupe_records(rows)


def name_colon_duty_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """姓名冒号职务型解析器，如“张三：党组书记、局长”；半结构不依赖词表。"""
    text = get_region_text(rule, html)
    rows: list[PersonRecord] = []
    for line in re.split(r"[\r\n]+", text):
        clean_line = compact_text(line)
        if not clean_line or len(clean_line) > 180:
            continue
        match = re.match(r"(?P<name>[一-鿿·\s　]{2,12})\s*[:：]\s*(?P<duty>.+)$", clean_line)
        if not match:
            continue
        duty = match.group("duty")
        if not ROLE_WORD_PATTERN.search(duty):
            continue
        record = make_record(
            rule=rule,
            name=match.group("name"),
            duty=duty,
            evidence=clean_line,
            parser=str(rule.get("parser", "V006_text_name_colon_duty_v1")),
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    lines = [compact_text(line) for line in re.split(r"[\r\n]+", text)]
    lines = [line for line in lines if line]
    for index, name_part in enumerate(lines[:-2]):
        colon_line = compact_text(lines[index + 1])
        duty = compact_text(lines[index + 2])
        if not re.fullmatch(r"[一-鿿·]{2,12}", name_part):
            continue
        if not re.fullmatch(r"[:：]", colon_line):
            continue
        if not duty or len(duty) > 180 or not ROLE_WORD_PATTERN.search(duty):
            continue
        record = make_record(
            rule=rule,
            name=name_part,
            duty=duty,
            evidence=f"{name_part}：{duty}",
            parser=str(rule.get("parser", "V006_text_name_colon_duty_v1")),
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    return dedupe_records(rows)


def yinchuan_name_colon_parenthesized_duty_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """银川市商务局领导分工页：解析“姓名：（完整职务）”段落。"""
    text = get_region_text(rule, html)
    rows: list[PersonRecord] = []
    parser_name = str(rule.get("parser", "S025_yinchuan_name_colon_parenthesized_duty_v1"))
    seen_names: set[str] = set()
    for match in re.finditer(r"(?P<name>[一-鿿·]{2,8})\s*[:：]\s*[（(](?P<duty>[^）)]{2,220})[）)]", text):
        name = match.group("name")
        duty = compact_text(match.group("duty")).strip(" ：:，,。.；;()（）")
        duty = re.sub(r"\s*([，,、；;])\s*", r"\1", duty)
        if name in seen_names or not duty or not ROLE_WORD_PATTERN.search(duty):
            continue
        seen_names.add(name)
        record = make_record(
            rule=rule,
            name=name,
            duty=duty,
            evidence=compact_text(match.group(0)),
            parser=parser_name,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    if rows:
        return dedupe_records(rows)
    for line in re.split(r"[\r\n]+", text):
        clean_line = compact_text(line)
        if not clean_line or len(clean_line) > 220:
            continue
        match = re.match(r"(?P<name>[一-鿿·]{2,8})\s*[:：]\s*[（(]?(?P<duty>.*?)[）)]?$", clean_line)
        if not match:
            continue
        duty = compact_text(match.group("duty")).strip(" ：:，,。.；;()（）")
        duty = re.sub(r"\s*([，,、；;])\s*", r"\1", duty)
        if not duty or not ROLE_WORD_PATTERN.search(duty):
            continue
        record = make_record(
            rule=rule,
            name=match.group("name"),
            duty=duty,
            evidence=clean_line,
            parser=parser_name,
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    return dedupe_records(rows)


def name_space_duty_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """姓名空格职务型解析器，如“张三 党组书记、局长”；半结构不依赖词表。"""
    text = get_region_text(rule, html)
    rows: list[PersonRecord] = []
    for line in re.split(r"[\r\n]+", text):
        clean_line = compact_text(line)
        if not clean_line or len(clean_line) > 160:
            continue
        match = re.match(r"(?P<name>[一-鿿·]{2,8})[\s　]+(?P<duty>.+)$", clean_line)
        if not match:
            continue
        if not is_compound_table_name(match.group("name")):
            continue
        duty = match.group("duty")
        if not ROLE_WORD_PATTERN.search(duty):
            continue
        record = make_record(
            rule=rule,
            name=match.group("name"),
            duty=duty,
            evidence=clean_line,
            parser=str(rule.get("parser", "V007_text_name_space_duty_v1")),
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    return dedupe_records(rows)


def name_nextline_duty_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """姓名职务相邻行解析器，如第一行姓名、下一行职务；半结构不依赖词表。"""
    text = get_region_text(rule, html)
    lines = [compact_text(line) for line in re.split(r"[\r\n]+", text)]
    lines = [line for line in lines if line]
    rows: list[PersonRecord] = []
    for index, line in enumerate(lines[:-1]):
        next_line = lines[index + 1]
        if not re.fullmatch(r"[一-鿿·]{2,8}", line):
            continue
        if ROLE_WORD_PATTERN.search(line):
            continue
        if not is_compound_table_name(line):
            continue
        if len(next_line) > 120 or not ROLE_WORD_PATTERN.search(next_line):
            continue
        record = make_record(
            rule=rule,
            name=line,
            duty=next_line,
            evidence=f"{line} {next_line}",
            parser=str(rule.get("parser", "V008_text_name_nextline_duty_v1")),
            snapshot_path=snapshot_path,
            apply_weak_wordlist=False,
        )
        if record:
            rows.append(record)
    return dedupe_records(rows)


def qinghai_slt_name_nextline_clean_duty_prefix_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """青海省水利厅页面：沿用相邻行解析，只清理“职务（职级）：”前缀。"""
    rows = name_nextline_duty_parser_v1(rule, html, final_url, snapshot_path)
    parser_name = str(rule.get("parser", "S026_qinghai_slt_name_nextline_clean_duty_prefix_v1"))
    repaired_rows: list[PersonRecord] = []
    for row in rows:
        row.duty = re.sub(r"^职务(?:（职级）)?\s*[:：]\s*", "", compact_text(row.duty)).strip(" ：:")
        row.parser = parser_name
        if row.name and row.duty:
            repaired_rows.append(row)
    return dedupe_records(repaired_rows)


def paragraph_profile_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """简历段落/正文混杂型解析器，按较可靠形态逐级尝试。"""
    parser_functions = [
        duty_colon_name_parser_v1,
        name_colon_duty_parser_v1,
        name_space_duty_parser_v1,
        name_nextline_duty_parser_v1,
    ]
    rows: list[PersonRecord] = []
    for parser_function in parser_functions:
        local_rule = dict(rule)
        local_rule["parser"] = parser_function.__name__
        rows.extend(parser_function(local_rule, html, final_url, snapshot_path))
    return dedupe_records(rows)


def profile_detail_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """详情正文弱结构解析器。"""
    return paragraph_profile_parser_v1(rule, html, final_url, snapshot_path)


def leader_directory_link_parser_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """目录页本身不产出人物职务，后续由详情页流程接管。"""
    return []


def parse_generic_confirmed_page(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    """兼容入口：先强结构明确选择器，再按页面类型有限兜底。"""
    parser = str(rule.get("parser", ""))
    if parser == "skip":
        return []
    rows = parse_strong_css_fields_v1(rule, html, final_url, snapshot_path)
    if rows:
        return rows
    if "card" in parser or "人物列表" in str(rule.get("page_type", "")):
        rows = card_person_parser_v1(rule, html, final_url, snapshot_path)
        if rows:
            return rows
    if str(rule.get("filter_policy", "")) == "weak_allow_wordlist":
        return paragraph_profile_parser_v1(rule, html, final_url, snapshot_path)
    return []
