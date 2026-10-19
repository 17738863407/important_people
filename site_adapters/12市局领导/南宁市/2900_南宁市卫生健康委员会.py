from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2900",
    "page_type": "职务分组名单页",
    "structure_group": "nanning_health_name_list_to_current_detail_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "online_http",
    "parser": "page_nanning_health_name_list_to_current_detail_v3",
    "leader_region_selector": "div.submain.w1100",
    "name_selector": "a[href^='./t'][href$='.html']",
    "duty_selector": "详情页 .article-content 首个以现任开头的段落",
    "detail_link_selector": "a[href^='./t'][href$='.html']",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 30},
    "risk_flag": "入口页只提供姓名；详情页现任句之后另有分工段落，禁止并入职务证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "div.submain.w1100", "name_selector": "a[href^='./t'][href$='.html']", "duty_selector": ".article-content p", "detail_link_selector": "a[href^='./t'][href$='.html']"}, "api": {"enabled": False, "reason": "领导目录和详情页现任句均为静态HTML直出"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """在线读取当前人物详情页，并按页面明确声明的UTF-8解码。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    return response.content.decode("utf-8")


def extract_current_duty(detail_html: str, expected_name: str) -> str:
    """校验详情页姓名，只取当前人物正文中的完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = normalize_layout(soup.title.get_text(" ", strip=True) if soup.title else "")
    if expected_name not in title:
        return ""
    for paragraph in soup.select(".article-content p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"现任(.{2,300})。", text)
        if match:
            return normalize_layout(match.group(1))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.submain.w1100")
    if region is None:
        return []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in region.select("a[href^='./t'][href$='.html']"):
        name = re.sub(r"\s+", "", anchor.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
        duty = extract_current_duty(fetch_detail_html(session, detail_url), name)
        if not duty:
            raise RuntimeError(f"人物详情页未提取到可回指的现任句：{name} {detail_url}")
        seen.add(name)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "入口人物链接按DOM顺序；详情.article-content完整现任句"})
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
