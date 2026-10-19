from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清除排版空白，不改变页面文本语义。"""
    text = re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", " ", value or "").strip()
    text = re.sub(r"\s*([，,、；;：:])\s*", r"\1", text)
    return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)


def compact_name(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200f\u202a-\u202e\u2060\u3000\xa0]+", "", value or "")


def is_hidden(element: Tag) -> bool:
    """排除当前节点或祖先中明确隐藏的内容。"""
    for node in [element, *element.parents]:
        if not isinstance(node, Tag):
            continue
        if node.has_attr("hidden") or str(node.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(node.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        classes = " ".join(str(item).lower() for item in node.get("class", []))
        if re.search(r"(?:^|[\s_-])(?:hidden|hide)(?:$|[\s_-])", classes):
            return True
    return False


def discover_people(html: str, final_url: str, group_path: str) -> list[tuple[str, str]]:
    """按页面 DOM 顺序取得目标领导分组的姓名和个人详情页。"""
    soup = BeautifulSoup(html or "", "html.parser")
    path_pattern = re.compile(rf"{re.escape(group_path)}/\d{{8}}/i\d+\.html$", re.IGNORECASE)
    people: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    for anchor in soup.select("a[href]"):
        if is_hidden(anchor):
            continue
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if detail_url in seen_urls or path_pattern.search(urlparse(detail_url).path) is None:
            continue
        name = compact_name(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) is None:
            continue
        if name in seen_names:
            raise RuntimeError(f"目标领导分组出现重复姓名：{name}")
        people.append((name, detail_url))
        seen_urls.add(detail_url)
        seen_names.add(name)
    if not people:
        raise RuntimeError(f"目标领导分组未发现个人详情页：{group_path}")
    return people


def extract_detail_duty(html: str, name: str) -> tuple[str, str]:
    """只在当前个人详情页中提取完整现职，不采集分工职责。"""
    soup = BeautifulSoup(html or "", "html.parser")
    name_pattern = re.escape(name)
    explicit: list[tuple[int, str, str]] = []
    for element in soup.select("h1, h2, h3, h4, p, div, span, li, td"):
        if is_hidden(element):
            continue
        original = clean_text(element.get_text(" ", strip=True))
        if not original or len(original) > 180:
            continue
        match = re.fullmatch(rf"(?P<duty>.+?)[：:]\s*{name_pattern}", original)
        if match is None:
            continue
        duty = clean_text(match.group("duty")).rstrip("，,；;。 ")
        if duty:
            explicit.append((len(original), duty, original))
    if explicit:
        _, duty, original = min(explicit, key=lambda item: item[0])
        return duty, original

    current: list[tuple[int, str, str]] = []
    for element in soup.select("p, div, span, li, td"):
        if is_hidden(element):
            continue
        original = clean_text(element.get_text(" ", strip=True))
        if not original or len(original) > 260 or name not in compact_name(original):
            continue
        match = re.search(r"现任\s*(?P<duty>[^。；;]+)", original)
        if match is None:
            continue
        duty = clean_text(match.group("duty")).rstrip("，,；;。 ")
        if duty:
            current.append((len(original), duty, original))
    if current:
        _, duty, original = min(current, key=lambda item: item[0])
        return duty, original
    raise RuntimeError(f"个人详情页未定位到当前职务：{name}")


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """从指定分组发现人物，再逐个进入个人详情页提取详细职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    group_path = str(page_rule["group_path"])
    rows: list[dict[str, str]] = []
    for name, detail_url in discover_people(html, final_url, group_path):
        if detail_url == final_url:
            detail_html = html
        else:
            page = fetch_html_with_strategy(
                detail_url, strategy="online", timeout=45, referer=final_url
            )
            detail_html = page.html
        duty, _original_evidence = extract_detail_duty(detail_html, name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "目标领导分组个人详情页中的当前职务字段",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "4483",
    "page_type": "领导之窗分组转个人详情页",
    "structure_group": "hnchangning_leader_window_detail_v1",
    "reuse_scope": "same_site_same_structure",
    "load_mode": "WAF 后在线页面；逐个请求个人详情页",
    "extract_mode": "list_to_detail",
    "parser": "page_hnchangning_leader_window_detail_v1",
    "group_path": "/zwgk/szfxxgkml/ldzc/szfzfsz",
    "leader_region_selector": "政府正副市长分组中的个人详情链接",
    "name_selector": "政府正副市长分组个人链接文本",
    "duty_selector": "个人详情页中的‘完整现职：姓名’或‘现任’字段",
    "detail_link_selector": "/ldzc/szfzfsz/YYYYMMDD/i数字.html",
    "detail_strategy": {"required": True, "mode": "current_person_detail"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "入口同时展示四组领导；严格按路径限定政府正副市长分组，并从个人页取现职，不取分工或履历",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
