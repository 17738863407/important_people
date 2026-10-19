from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1978",
    "page_type": "职务分组名单页",
    "structure_group": "npc_committee_member_iframe_groups",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http_iframe",
    "leader_region_selector": "iframe[src^='./']",
    "name_selector": ".right_xinxi .list1, .right_xinxi .text1 + .text2",
    "risk_flag": "入口含页头、工作动态、名单和页脚多个iframe，只能解析具备委员会角色结构的同源frame",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def _space_width(value: str) -> int:
    return sum(2 if char == "\u3000" else 1 for char in value)


def _split_visual_fields(value: str) -> list[str]:
    fields: list[str] = []
    start = 0
    for match in re.finditer(r"\s+", value):
        if _space_width(match.group()) < 4:
            continue
        field = value[start : match.start()].strip()
        if field:
            fields.append(field)
        start = match.end()
    tail = value[start:].strip()
    if tail:
        fields.append(tail)
    return fields


def _segment_name_field(value: str) -> list[tuple[str, str]]:
    raw_value = value.strip()
    plain_value = re.sub(r"（[^）]*）", "", raw_value)
    chars: list[str] = []
    gaps: list[int] = []
    pending_gap = 0
    for char in plain_value:
        if "\u3400" <= char <= "\u9fff" or char == "·":
            if chars:
                gaps.append(pending_gap)
            chars.append(char)
            pending_gap = 0
        elif char.isspace():
            pending_gap += _space_width(char)
    if not chars:
        return []

    best: list[tuple[int, list[str]]] | None = [(0, [])] + [(-10_000, []) for _ in chars]
    for index in range(len(chars)):
        score, names = best[index]
        if score <= -10_000:
            continue
        for length in (3, 2):
            end = index + length
            if end > len(chars):
                continue
            internal_gaps = gaps[index : end - 1]
            if length == 2:
                gain = 6 if internal_gaps and internal_gaps[0] > 0 else 0
            else:
                gain = 3 if all(gap == 0 for gap in internal_gaps) else -3
            candidate = (score + gain, names + ["".join(chars[index:end])])
            if candidate[0] > best[end][0]:
                best[end] = candidate
    score, names = best[len(chars)]
    if score <= -10_000:
        return []
    annotation = "".join(re.findall(r"（[^）]*）", raw_value))
    return [(name, name + annotation if len(names) == 1 else name) for name in names]


def _split_names(container: Tag) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = []
    paragraphs = container.select("p") or [container]
    for paragraph in paragraphs:
        raw_line = paragraph.get_text("", strip=True)
        for field in _split_visual_fields(raw_line):
            names.extend(_segment_name_field(field))
    return names


def _append_group(
    rows: list[dict[str, str]],
    duty: str,
    people: list[tuple[str, str]],
    evidence: str,
    page_rule: dict[str, object],
) -> None:
    for name, _ in people:
        if not re.fullmatch(r"[一-鿿·]{2,4}", name):
            continue
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_npc_committee_member_iframe_groups_v1",
            }
        )


def _parse_member_frame(frame_html: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(frame_html, "html.parser")
    region = soup.select_one("div.right_xinxi")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    director_items = region.select(".list1 li")
    if len(director_items) >= 2:
        duty = _clean_text(director_items[0].get_text(" ", strip=True))
        raw_name = director_items[1].get_text("", strip=True)
        people = _segment_name_field(raw_name)
        _append_group(rows, duty, people, _clean_text(f"{duty} {raw_name}"), page_rule)

    for heading in region.select(":scope > div.text1"):
        names_container = heading.find_next_sibling("div", class_="text2")
        if names_container is None:
            continue
        heading_text = _clean_text(heading.get_text(" ", strip=True))
        duty = re.sub(r"（[^）]*）", "", heading_text).strip()
        if duty == "委员":
            continue
        people = _split_names(names_container)
        raw_names = _clean_text(names_container.get_text(" ", strip=True))
        _append_group(rows, duty, people, _clean_text(f"{heading_text} {raw_names}"), page_rule)
    return rows


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态发现并解析当前委员会组成人员iframe。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    for frame in soup.select("iframe[src^='./']"):
        frame_url = urljoin(final_url, str(frame.get("src") or ""))
        response = session.get(frame_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        rows = _parse_member_frame(response.text, page_rule)
        if rows:
            return rows
    raise RuntimeError("入口的同源相对iframe中未发现委员会组成人员结构")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
