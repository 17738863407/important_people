from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from crawler_core.models import PersonRecord
from crawler_core.utils import clean_name, compact_text


PARSER_NAME = "S027_baidu_baike_leader_section_v1"

REFERENCE_PATTERN = re.compile(r"\[\s*\d+(?:\s*[-–—]\s*\d+)?(?:\s*[,，、]\s*\d+)*\s*\]")
ROLE_PATTERN = re.compile(
    r"书记|副书记|常委|主席|副主席|主任|副主任|巡视员|秘书长|副秘书长|"
    r"会长|副会长|常务副会长|党组成员|党委委员|委员"
)
ROLE_ONLY_PATTERN = re.compile(
    r"^(?:党组|党委|市委|市政协|人大常委会|常务委员会)?(?:成员、?)?"
    r"(?:书记|副书记|常委|主席|副主席|主任|副主任|巡视员|秘书长|副秘书长|"
    r"会长|副会长|常务副会长|党组成员|党委委员|委员)"
    r"(?:、(?:一级|二级)?巡视员|、党组成员|、党委委员|、副主任|、副主席)*$"
)
PERSON_TOKEN_PATTERN = re.compile(r"[\u3400-\u9fff·]{2,20}(?:（[^（）]{1,40}）)?")
DEMOGRAPHIC_OR_STATUS_PATTERN = re.compile(
    r"^(?:女|男|回族|满族|蒙古族|藏族|维吾尔族|哈萨克族|苗族|土家族|"
    r"\d{4}年\d{1,2}月当选|兼|兼职)$"
)
DEMOGRAPHIC_WORDS = {
    "女",
    "男",
    "回族",
    "满族",
    "蒙古族",
    "藏族",
    "维吾尔族",
    "哈萨克族",
    "苗族",
    "土家族",
}
SKIP_LINE_PATTERN = re.compile(
    r"^(?:截至.+如下|中国.+(?:会长|领导班子).+|照片|姓名与职务|参考资料|参\s*考\s*资\s*料|"
    r"按.+顺序排列|暂无|-)$"
)
INVALID_NAME_PATTERN = re.compile(r"^(?:暂无|回族|满族|资料来源|来源|以上按顺序排列|顺序排列)$")


def _clean_baike_text(value: object) -> str:
    """清理百度百科引用序号和由行内节点造成的中文断裂空格。"""
    text = compact_text(value)
    text = REFERENCE_PATTERN.sub("", text)
    text = text.replace("播报", "").replace("编辑", "")
    previous = ""
    while previous != text:
        previous = text
        text = re.sub(r"(?<=[\u3400-\u9fff·])\s+(?=[\u3400-\u9fff·])", "", text)
    text = re.sub(r"\s*([：:，,、；;。])\s*", r"\1", text)
    text = re.sub(r"([，,、；;。])\1+", r"\1", text)
    text = re.sub(r"（\s+", "（", text)
    text = re.sub(r"\s+）", "）", text)
    return compact_text(text)


def _clean_duty(value: object) -> str:
    """生成仍可回指原文的确定性职务证据。"""
    text = _clean_baike_text(value)
    text = re.sub(r"^现任", "", text, count=1)
    return text.strip(" ：:，,、；;。")


def _normalized_name(value: object, project_dir: Path) -> str:
    """去除姓名括注和排版空格后按项目姓名规则校验。"""
    text = _clean_baike_text(value)
    text = re.sub(r"（[^（）]*）", "", text)
    return clean_name(text, project_dir)


def _split_name_and_note(value: object, project_dir: Path) -> tuple[str, str]:
    """从名单项中分离姓名与可能承载附加职务的括注。"""
    text = _clean_baike_text(value).strip(" ：:，,、；;。")
    note_match = re.fullmatch(r"(.+?)（([^（）]+)）", text)
    note = ""
    if note_match:
        text = note_match.group(1)
        raw_note = _clean_duty(note_match.group(2))
        note_parts = {part for part in re.split(r"[、，,]+", raw_note) if part}
        if (
            raw_note
            and not DEMOGRAPHIC_OR_STATUS_PATTERN.fullmatch(raw_note)
            and not (note_parts and note_parts <= DEMOGRAPHIC_WORDS)
        ):
            note = raw_note
    return clean_name(text, project_dir), note


def _is_role_only(value: object) -> bool:
    text = _clean_duty(value).replace("其他", "")
    if not text or len(text) > 32 or re.search(r"[:：。；;]", text):
        return False
    # “姓名（一级巡视员）、姓名（一级巡视员）”属于人物名单，不能因含职务词而误判为分组标题。
    leading_text = re.split(r"[（、，,]", text, maxsplit=1)[0]
    leading_name = re.sub(r"\s+", "", leading_text)
    if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", leading_name) and not ROLE_PATTERN.search(leading_text):
        return False
    return bool(ROLE_ONLY_PATTERN.fullmatch(text) or ROLE_PATTERN.search(text))


def _canonical_detail_url(href: str, base_url: str) -> str:
    """保留可验证的百度百科人物词条链接，并移除展示来源参数。"""
    absolute = urljoin(base_url, href.strip())
    parts = urlsplit(absolute)
    if parts.netloc != "baike.baidu.com" or not parts.path.startswith("/item/"):
        return ""
    return urlunsplit((parts.scheme or "https", parts.netloc, parts.path, "", ""))


def _person_links(node: Tag, base_url: str, project_dir: Path) -> dict[str, str]:
    """建立当前人物区域内“姓名—独立百科词条”的可验证映射。"""
    links: dict[str, str] = {}
    for link in node.select("a[href]"):
        name = _normalized_name(link.get_text(" ", strip=True), project_dir)
        detail_url = _canonical_detail_url(str(link.get("href", "")), base_url)
        if name and detail_url:
            links.setdefault(name, detail_url)
    return links


def _append_record(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    project_dir: Path,
    name_value: object,
    duty_value: object,
    detail_links: dict[str, str],
    snapshot_path: Path | None,
) -> None:
    """校验姓名和职务后按页面顺序追加一条记录。"""
    name = _normalized_name(name_value, project_dir)
    duty = _clean_duty(duty_value)
    if not name or INVALID_NAME_PATTERN.fullmatch(name) or not duty:
        return
    rows.append(
        PersonRecord(
            organization=str(rule.get("organization", "")),
            url=str(rule.get("url", "")),
            name=name,
            duty=duty,
            detail_url=detail_links.get(name, ""),
            evidence=duty,
            confidence=str(rule.get("confidence", "高")),
            parser=PARSER_NAME,
            snapshot_path=str(snapshot_path or ""),
        )
    )


def _split_name_list(value: object) -> list[str]:
    """拆分“职务：多人名单”，不按空格拆分少数民族姓名。"""
    text = _clean_baike_text(value).strip(" ：:，,、；;。")
    if not text:
        return []
    parts: list[str] = []
    current: list[str] = []
    parenthesis_depth = 0
    for character in text:
        if character == "（":
            parenthesis_depth += 1
        elif character == "）" and parenthesis_depth:
            parenthesis_depth -= 1
        if character in "、，,；;" and parenthesis_depth == 0:
            token = "".join(current).strip()
            if token:
                parts.append(token)
            current = []
            continue
        current.append(character)
    token = "".join(current).strip()
    if token:
        parts.append(token)
    return parts


def _append_role_name_list(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    project_dir: Path,
    role: str,
    names_text: object,
    detail_links: dict[str, str],
    snapshot_path: Path | None,
) -> None:
    """按网页名单顺序把同一职务对应的多人展开为逐人记录。"""
    clean_role = _clean_duty(role)
    for token in _split_name_list(names_text):
        name, note = _split_name_and_note(token, project_dir)
        if not name:
            continue
        duty = clean_role
        if note and rule.get("baike_parenthetical_duty_overrides_role"):
            duty = note
        elif note and note not in duty:
            duty = f"{duty}、{note}" if duty else note
        _append_record(rows, rule, project_dir, name, duty, detail_links, snapshot_path)


def _name_before_colon(value: str, links: dict[str, str], project_dir: Path) -> str:
    """识别冒号左侧姓名，兼容图片表格中重复展示的姓名。"""
    left = _clean_baike_text(value).strip(" ：:，,、；;。")
    linked_names = [name for name in links if name in left]
    if linked_names:
        return linked_names[-1]
    compact = re.sub(r"\s+", "", left)
    if len(compact) % 2 == 0 and compact[: len(compact) // 2] == compact[len(compact) // 2 :]:
        compact = compact[: len(compact) // 2]
    return clean_name(compact, project_dir)


def _parse_text_line(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    project_dir: Path,
    text_value: object,
    detail_links: dict[str, str],
    snapshot_path: Path | None,
    current_role: str,
) -> str:
    """解析段落中的姓名职务对，并返回可能更新后的分组职务。"""
    text = _clean_baike_text(text_value)
    if not text or SKIP_LINE_PATTERN.fullmatch(text) or text.startswith("（按"):
        return current_role
    if _is_role_only(text):
        return _clean_duty(text).replace("其他", "")

    sentence_parts = [part for part in re.split(r"[。；;]+", text) if part]
    if len(sentence_parts) > 1 and sum(bool(re.search(r"[:：]", part)) for part in sentence_parts) > 1:
        next_role = current_role
        for part in sentence_parts:
            next_role = _parse_text_line(
                rows,
                rule,
                project_dir,
                part,
                detail_links,
                snapshot_path,
                next_role,
            )
        return next_role

    colon_match = re.search(r"[:：]", text)
    if colon_match:
        left = text[: colon_match.start()]
        right = text[colon_match.end() :]
        if _is_role_only(left):
            role = _clean_duty(left).replace("其他", "")
            _append_role_name_list(rows, rule, project_dir, role, right, detail_links, snapshot_path)
            return role
        name = _name_before_colon(left, detail_links, project_dir)
        if name:
            _append_record(rows, rule, project_dir, name, right or current_role, detail_links, snapshot_path)
            return current_role

    if current_role:
        linked_names = list(detail_links)
        if linked_names and not any(separator in text for separator in "、，,；;"):
            for name in linked_names:
                _append_record(rows, rule, project_dir, name, current_role, detail_links, snapshot_path)
            return current_role
        _append_role_name_list(rows, rule, project_dir, current_role, text, detail_links, snapshot_path)
    return current_role


def _parse_table(
    rows: list[PersonRecord],
    rule: dict[str, Any],
    project_dir: Path,
    table: Tag,
    final_url: str,
    snapshot_path: Path | None,
    current_role: str,
) -> str:
    """解析百度百科领导栏目中的单列表、角色分组表和姓名职务表。"""
    for table_row in table.select("tr"):
        cells = table_row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        texts = [_clean_baike_text(cell.get_text(" ", strip=True)) for cell in cells]
        links = _person_links(table_row, final_url, project_dir)
        if not any(texts) or any(text in {"照片", "姓名与职务", "姓名", "职务"} for text in texts):
            continue
        if len(cells) == 1:
            current_role = _parse_text_line(
                rows, rule, project_dir, texts[0], links, snapshot_path, current_role
            )
            continue

        first, second = texts[0], texts[1]
        if _is_role_only(first):
            current_role = _clean_duty(first).replace("其他", "")
            _append_role_name_list(rows, rule, project_dir, current_role, second, links, snapshot_path)
            continue

        first_name = _normalized_name(first, project_dir)
        if first_name:
            duty = second
            colon_match = re.search(r"[:：]", second)
            if colon_match and _name_before_colon(second[: colon_match.start()], links, project_dir):
                duty = second[colon_match.end() :]
            _append_record(rows, rule, project_dir, first_name, duty or current_role, links, snapshot_path)
            continue

        current_role = _parse_text_line(
            rows, rule, project_dir, second, links, snapshot_path, current_role
        )
    return current_role


def _section_nodes(root: Tag, section_titles: set[str]) -> Iterable[Tag]:
    """取得目标栏目到下一个同级或更高层级栏目之间的顶层节点。"""
    target: Tag | None = None
    for header in root.select('div[data-tag="header"][data-level]'):
        title = _clean_baike_text(header.get("data-name") or header.get_text(" ", strip=True))
        if title in section_titles:
            target = header
            break
    if target is None:
        yield from (child for child in root.children if isinstance(child, Tag))
        return
    target_level = int(str(target.get("data-level") or "1"))
    current = target.find_next_sibling()
    while isinstance(current, Tag):
        if current.get("data-tag") == "header":
            current_level = int(str(current.get("data-level") or "1"))
            if current_level <= target_level:
                break
        yield current
        current = current.find_next_sibling()


def _dedupe_exact_rows(rows: list[PersonRecord]) -> list[PersonRecord]:
    """仅去除完全相同的重复展示，不合并不同职务证据。"""
    result: list[PersonRecord] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row.name, row.duty, row.detail_url)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _merge_same_name_duties(rows: list[PersonRecord]) -> list[PersonRecord]:
    """按页面脚本显式授权合并同一人物的多项现职，并保持首次出现顺序。"""
    result: list[PersonRecord] = []
    by_name: dict[str, PersonRecord] = {}
    for row in rows:
        current = by_name.get(row.name)
        if current is None:
            by_name[row.name] = row
            result.append(row)
            continue
        existing_duties = [part for part in current.duty.split("；") if part]
        if row.duty not in existing_duties:
            current.duty = "；".join([*existing_duties, row.duty])
            current.evidence = current.duty
        if not current.detail_url and row.detail_url:
            current.detail_url = row.detail_url
    return result


def parse_baidu_baike_leader_section_v1(
    rule: dict[str, Any],
    html: str,
    final_url: str,
    snapshot_path: Path | None,
) -> list[PersonRecord]:
    """解析百度百科半结构化现任领导栏目，严格限制在页面脚本指定的栏目内。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".J-lemma-content")
    if not isinstance(root, Tag):
        return []

    section_titles = {
        _clean_baike_text(title)
        for title in rule.get("baike_section_titles", [])
        if _clean_baike_text(title)
    }
    if not section_titles:
        return []
    start_marker = _clean_baike_text(rule.get("baike_start_marker", ""))
    marker_reached = not start_marker
    project_dir = Path(__file__).resolve().parents[1]
    rows: list[PersonRecord] = []
    current_role = ""

    for node in _section_nodes(root, section_titles):
        node_text = _clean_baike_text(node.get_text(" ", strip=True))
        if not marker_reached:
            if start_marker and start_marker in node_text:
                marker_reached = True
            continue
        if node.get("data-tag") == "header" and str(node.get("data-level", "")) != "1":
            header_text = _clean_duty(node.get("data-name") or node_text).replace("其他", "")
            if _is_role_only(header_text):
                current_role = header_text
            continue
        if node.get("data-tag") == "module" and not rule.get("baike_allow_module_tables"):
            continue
        tables = node.select("table") if node.name != "table" else [node]
        if tables:
            for table in tables:
                current_role = _parse_table(
                    rows, rule, project_dir, table, final_url, snapshot_path, current_role
                )
            continue
        if node.get("data-tag") not in {"paragraph", "list"}:
            continue
        links = _person_links(node, final_url, project_dir)
        current_role = _parse_text_line(
            rows, rule, project_dir, node_text, links, snapshot_path, current_role
        )

    deduped_rows = _dedupe_exact_rows(rows)
    if rule.get("baike_merge_same_name_duties"):
        return _merge_same_name_duties(deduped_rows)
    return deduped_rows
