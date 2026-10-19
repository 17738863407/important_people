from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3778",
    "domain": "baike.baidu.com",
    "page_type": "百科词条市委领导分节",
    "load_mode": "浏览器渲染DOM",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "page_inline",
    "collector": "browser_dom",
    "parser": "page_inline_baike_leadership_heading_sections_v1",
    "leader_region_selector": "h2",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "市委领导",
        "end_anchor": "办公地址",
        "include_selectors": ["h2", "h3"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "按用户指定仅抽取百度百科‘市委领导’版块；百度百科可能动态更新或呈现不同版本，且来源并非官方页面",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def normalize_duty(value: str) -> str:
    """将同一人物的并列职务统一为全角分号分隔。"""
    return "；".join(part.strip(" ，,；;。") for part in re.split(r"[、，,；;]", clean_text(value)) if part.strip(" ，,；;。"))


def collect_section(heading: Tag, final_url: str) -> tuple[str, dict[str, str]]:
    """提取一个三级标题至下一个二、三级标题之间的正文和人物链接。"""
    text_parts: list[str] = []
    detail_urls: dict[str, str] = {}
    for element in heading.next_elements:
        if isinstance(element, Tag) and element is not heading and element.name in {"h2", "h3"}:
            break
        if isinstance(element, Tag) and element.name == "a" and element.get("href"):
            link_text = re.sub(r"\s+", "", clean_text(element.get_text(" ", strip=True)))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", link_text):
                detail_urls[link_text] = urljoin(final_url, str(element.get("href", "")))
        if not isinstance(element, NavigableString):
            continue
        parent = element.parent
        if parent is None or parent.find_parent(["sup", "script", "style"]):
            continue
        if parent is heading or heading in parent.parents:
            continue
        value = str(element).strip()
        if value:
            text_parts.append(value)
    section_text = re.sub(r"\[\d+(?:-\d+)?\]", "", "".join(text_parts))
    return clean_text(section_text), detail_urls


def parse_named_duties(section_text: str, detail_urls: dict[str, str]) -> list[tuple[str, str]]:
    """依据段首姓名和人物链接锚点切分“姓名：职务”连续文本。"""
    positions: dict[int, tuple[str, int]] = {}
    first_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,5})[：:]", section_text)
    if first_match:
        positions[first_match.start()] = (first_match.group("name"), first_match.end())
    for name in detail_urls:
        for match in re.finditer(rf"{re.escape(name)}[：:]", section_text):
            positions[match.start()] = (name, match.end())

    ordered_positions = sorted(positions.items())
    parsed: list[tuple[str, str]] = []
    for index, (_, (name, duty_start)) in enumerate(ordered_positions):
        duty_end = ordered_positions[index + 1][0] if index + 1 < len(ordered_positions) else len(section_text)
        duty = section_text[duty_start:duty_end].strip(" ，,、；;。")
        if duty:
            parsed.append((name, duty))
    return parsed


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅从“市委领导”下的书记、副书记和市委常委分节动态解析。"""
    soup = BeautifulSoup(html, "html.parser")
    leadership_heading = next(
        (node for node in soup.find_all("h2") if clean_text(node.get_text(" ", strip=True)) == "市委领导"),
        None,
    )
    if leadership_heading is None:
        raise RuntimeError("页面未找到‘市委领导’二级标题")

    section_headings: list[Tag] = []
    for heading in leadership_heading.find_all_next(["h2", "h3"]):
        if heading is leadership_heading:
            continue
        if heading.name == "h2":
            break
        if clean_text(heading.get_text(" ", strip=True)) in {"书记", "副书记", "市委常委"}:
            section_headings.append(heading)
    if not section_headings:
        raise RuntimeError("‘市委领导’版块下未找到书记、副书记或市委常委分节")

    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}

    def append_or_merge_row(name: str, duty: str, detail_url: str = "") -> None:
        normalized_name = re.sub(r"\s+", "", name)
        normalized_duty = normalize_duty(duty)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", normalized_name):
            return
        if not normalized_duty:
            return
        if normalized_name in row_by_name:
            row = row_by_name[normalized_name]
            duties = row["duty"].split("；")
            for duty_part in normalized_duty.split("；"):
                if duty_part not in duties:
                    duties.append(duty_part)
            row["duty"] = "；".join(duties)
            row["evidence"] = row["duty"]
            if not row["detail_url"] and detail_url:
                row["detail_url"] = detail_url
            return
        row = {
            "name": normalized_name,
            "duty": normalized_duty,
            "evidence": normalized_duty,
            "detail_url": detail_url,
            "confidence": "low",
            "parser": str(page_rule.get("parser", "")),
        }
        row_by_name[normalized_name] = row
        rows.append(row)

    for section_heading in section_headings:
        section_text, detail_urls = collect_section(section_heading, final_url)
        for name, duty in parse_named_duties(section_text, detail_urls):
            append_or_merge_row(name, duty, detail_urls.get(name, ""))

    if not rows:
        raise RuntimeError("‘市委领导’版块未形成可验证的领导记录")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
