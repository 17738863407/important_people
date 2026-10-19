from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3713",
    "page_type": "人物列表转详情页",
    "structure_group": "cnips_leader_article_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_cnips_leader_article_v1",
    "leader_region_selector": ".research-introduct .news-con",
    "name_selector": ".research-introduct .news-con p",
    "duty_selector": ".research-introduct .news-con strong",
    "detail_link_selector": ".research-introduct .news-con a[href]",
    "content_scope": {"start_anchor": "会领导", "end_anchor": "友情链接", "include_selectors": [".research-introduct .news-con"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "dynamic_image_link_title", "max_detail_links": 5},
    "risk_flag": "理事长姓名仅由页面头像链接的独立详情页标题给出；副理事长名单用连续不间断空格排版且含单字分隔姓名；同一人兼任秘书长须合并职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_heading_lists_and_detail_title",
    "locator": {"css": {"container_selector": ".research-introduct .news-con", "heading_selector": "strong", "detail_selector": "a[href] img"}, "api": {"enabled": False, "reason": "列表正文和动态详情页标题均由静态HTML直接提供"}, "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def normalize_name(value: str) -> str:
    value = re.sub(r"（[^）]*）", "", value)
    return re.sub(r"\s+", "", value)


def add_person(rows: list[dict[str, str]], positions: dict[str, int], name: str, duty: str, detail_url: str, page_rule: dict) -> None:
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
        return
    if name in positions:
        row = rows[positions[name]]
        duties = row["duty"].split("；")
        if duty not in duties:
            row["duty"] = f'{row["duty"]}；{duty}'
            row["source_text"] = row["duty"]
        return
    positions[name] = len(rows)
    rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_article；order=page_order"})


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".research-introduct .news-con")
    if container is None:
        return []
    rows: list[dict[str, str]] = []
    positions: dict[str, int] = {}
    portrait_link = container.select_one("a[href] img")
    if portrait_link is not None and portrait_link.parent is not None:
        detail_url = urljoin(final_url, str(portrait_link.parent.get("href") or "").strip())
        if detail_url:
            response = requests.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            detail_soup = BeautifulSoup(response.text, "html.parser")
            title = clean_text(detail_soup.title.get_text(" ", strip=True) if detail_soup.title else "")
            match = re.match(r"(?P<duty>理事长)\s+(?P<name>[\u4e00-\u9fff·]{2,8})\s*[-－]", title)
            if match:
                add_person(rows, positions, match.group("name"), match.group("duty"), detail_url, page_rule)
    current_duty = ""
    for paragraph in container.select("p"):
        if paragraph.find("p") is not None:
            continue
        text = paragraph.get_text(" ", strip=True)
        if not clean_text(text):
            continue
        strong = paragraph.find("strong")
        if strong is not None:
            heading = clean_text(strong.get_text(" ", strip=True))
            current_duty = re.sub(r"（\d+人[^）]*）", "", heading).strip()
            continue
        if not current_duty:
            continue
        text = re.sub(r"（[^）]*）", "\xa0\xa0\xa0\xa0", text)
        for item in re.split(r"\xa0{4,}", text):
            name = normalize_name(item)
            add_person(rows, positions, name, current_duty, "", page_rule)
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
