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
    "rule_id": "3766",
    "domain": "www.gsagr.cn",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_gsagr_leaders_v1",
    "leader_region_selector": ".ny-right .ldtz",
    "name_selector": ".ldtz-info h3",
    "duty_selector": ".ldtz-info p",
    "detail_link_selector": "li > a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导卡片顺序提取姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".ny-right .ldtz li"):
        link = item.select_one(":scope > a[href]")
        name_node = item.select_one(".ldtz-info h3")
        duty_node = item.select_one(".ldtz-info p")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": urljoin(base_url, str(link.get("href", ""))) if link else "",
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
