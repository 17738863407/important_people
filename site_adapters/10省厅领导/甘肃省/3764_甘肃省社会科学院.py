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
    "rule_id": "3764",
    "domain": "www.gsass.net.cn",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_gsass_leaders_v1",
    "leader_region_selector": ".mainContent .mBd",
    "name_selector": ".title h3 a",
    "duty_selector": ".title span, .intro p",
    "detail_link_selector": ".title h3 a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "部分职务拆分在多个段落中",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导卡片顺序提取姓名、职务和真实详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".mainContent .mBd")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in region.select("li"):
        name_link = item.select_one(".title h3 a")
        if not name_link:
            continue
        name = re.sub(r"\s+", "", clean_text(name_link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        duty_parts = [clean_text(node.get_text(" ", strip=True)) for node in item.select(".title span")]
        if not duty_parts:
            duty_parts = [clean_text(node.get_text(" ", strip=True)) for node in item.select(".intro p")]
        duty_parts = [part for part in duty_parts if part]
        if not duty_parts:
            continue
        seen.add(name)
        detail_url = urljoin(base_url, str(name_link.get("href", "")))
        rows.append({
            "name": name,
            "duty": "；".join(dict.fromkeys(duty_parts)),
            "evidence": "；".join(dict.fromkeys(duty_parts)),
            "detail_url": detail_url,
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
        })
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
