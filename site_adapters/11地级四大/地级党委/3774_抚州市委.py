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
    "rule_id": "3774",
    "domain": "www.jxfz.gov.cn",
    "page_type": "人物详情与同机构分组名单同页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_fuzhou_party_leaders_v1",
    "leader_region_selector": ".main01_r01 .ldl",
    "name_selector": "li a.a20[href]",
    "duty_selector": "li > div:first-of-type",
    "detail_link_selector": "li a.a20[href]",
    "content_scope": {"start_anchor": "市委领导", "end_anchor": "", "include_selectors": [".main01_r01 .ldl"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "页面同时显示当前人物详情与完整市委名单，以右侧市委分组名单为准",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按书记、副书记、常委三个页面分组抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".main01_r01 .ldl")
    if not region:
        return []
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for item in region.find_all("li", recursive=False):
        direct_divs = item.find_all("div", recursive=False)
        if len(direct_divs) < 2:
            continue
        duty = re.sub(r"\s+", "", clean_text(direct_divs[0].get_text(" ", strip=True)))
        for link in direct_divs[1].select("a.a20[href]"):
            name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
                continue
            detail_url = urljoin(base_url, str(link.get("href", "")))
            if detail_url.rstrip("/") == base_url.rstrip("/"):
                detail_url = ""
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url, "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
