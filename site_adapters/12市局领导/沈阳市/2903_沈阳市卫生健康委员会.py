from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2903", "page_type": "人物目录详情页", "structure_group": "shenyang_health_labeled_details_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_health_labeled_details_v2",
    "leader_region_selector": "ul.ldzp li", "name_selector": "a[href] span",
    "duty_selector": "详情.view内职务标签至工作分工标签", "detail_link_selector": "ul.ldzp li a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "详情工作分工不得混入原始职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录顺序在线抓取详情页的姓名与职务强标签字段。"""
    from crawler_core.fetcher import fetch_online_html
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    base_node = soup.find("base", href=True)
    base_url = urljoin(final_url, str(base_node.get("href", ""))) if base_node else final_url
    links = soup.select("ul.ldzp li a[href]")
    if not links:
        raise RuntimeError("人物目录没有找到详情链接")
    records: list[object] = []
    seen_names: set[str] = set()
    for link in links:
        name_node = link.select_one("span")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        detail_url = urljoin(base_url, str(link.get("href", "")).strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not detail_url:
            raise RuntimeError("人物目录姓名或详情链接异常")
        detail_html, detail_final_url = fetch_online_html(detail_url)
        detail = BeautifulSoup(detail_html or "", "html.parser")
        views = detail.select(".view")
        if len(views) != 1:
            raise RuntimeError(f"人物详情正文数量异常：{name}={len(views)}")
        text = clean_text(views[0].get_text(" ", strip=True))
        match = re.search(r"姓名：\s*(?P<name>.+?)\s+职务：\s*(?P<duty>.+?)\s+工作分工：", text)
        if match is None or re.sub(r"\s+", "", match.group("name")) != name:
            raise RuntimeError(f"人物详情姓名或职务标签异常：{name}")
        evidence = clean_text(match.group("duty"))
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物详情职务为空或姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_final_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
