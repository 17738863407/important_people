from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2286", "page_type": "人物列表完整页",
    "structure_group": "haikou_finance_leader_cards", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "requests", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "builtin_parse_page", "leader_region_selector": ".gkpd-l-nr",
    "name_selector": "a[href] .ldmc", "duty_selector": "a[href] .ldzw",
    "detail_link_selector": "a[href]:has(.ldmc):has(.ldzw)",
    "detail_strategy": {"required": False, "mode": "links_from_listing", "max_detail_links": 50},
    "risk_flag": "首卡链接指向站点首页而非人物详情，必须清空；其余详情链接按人物卡片动态保留",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def valid_detail_url(url: str, entry_url: str) -> str:
    parsed = urlparse(url)
    if not parsed.path or parsed.path == "/" or url == entry_url:
        return ""
    return url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select(".gkpd-l-nr a[href]:has(.ldmc):has(.ldzw)"):
        name_node = link.select_one(".ldmc")
        duty_node = link.select_one(".ldzw")
        if name_node is None or duty_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True)).strip("[]【】")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,12}", name) or not duty:
            continue
        detail_url = valid_detail_url(urljoin(final_url, str(link.get("href") or "")), final_url)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url,
                     "selector_summary": ".gkpd-l-nr人物卡片.ldmc姓名与.ldzw职务"})
    if not rows:
        raise ValueError("财政局领导区域未发现有效姓名职务卡片")
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
