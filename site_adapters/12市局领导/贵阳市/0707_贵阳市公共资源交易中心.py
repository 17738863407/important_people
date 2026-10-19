from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0707", "page_type": "人物列表完整页", "structure_group": "人物目录链接与详情基本信息字段块",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "list_to_detail", "collector": "online", "parser": "builtin_parse_page",
    "leader_region_selector": "a[href*='/jgld_5978106/']", "name_selector": "a[href*='/jgld_5978106/']", "duty_selector": ".ldjbxx",
    "detail_link_selector": "a[href*='/jgld_5978106/']", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["a[href*='/jgld_5978106/']"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 50},
    "risk_flag": "详情页姓名、职务和简历同区块，必须以字段标签截断，排除简历与领导分工", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def read_detail(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".ldjbxx")
    if root is None:
        return "", ""
    text = clean_text(root.get_text(" ", strip=True))
    name_match = re.search(r"姓名\s*[：:]\s*(?P<name>[\u4e00-\u9fff·]{2,4})", text)
    duty_match = re.search(r"职务\s*[：:]\s*(?P<duty>.+?)\s*简历\s*[：:]", text)
    return (name_match.group("name") if name_match else "", clean_text(duty_match.group("duty")) if duty_match else "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录顺序抓取详情，并读取基本信息区块的姓名与职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a[href*='/jgld_5978106/']"):
        listed_name = clean_text(link.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", listed_name) is None or listed_name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        detail = fetch_html_with_strategy(detail_url, "requests")
        name, duty = read_detail(detail.html)
        if not name or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail.final_url, "selector_summary": "人物目录链接；详情.ldjbxx姓名与职务标签值"})
        seen.add(name)
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
