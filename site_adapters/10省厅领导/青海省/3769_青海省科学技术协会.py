from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3769",
    "domain": "www.qast.org.cn",
    "page_type": "同页多组领导名单",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qast_leaders_v1",
    "leader_region_selector": "div.kxld",
    "name_selector": ".kxld_card > p i, .kxld_card_sm .name",
    "duty_selector": ".kxld_card > p span, .kxld_card_sm .pos",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "同一人物在党组和协会职务组重复出现，需按页面顺序合并",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """依页面分组顺序抽取，并合并同一人物的不同现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.kxld")
    if not region:
        return []
    ordered: dict[str, list[str]] = {}
    for node in region.select(".kxld_card > p, .kxld_card_sm"):
        name_node = node.select_one(":scope > i, .name")
        duty_node = node.select_one(":scope > span, .pos")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        duties = ordered.setdefault(name, [])
        if duty not in duties:
            duties.append(duty)
    return [
        {
            "name": name,
            "duty": "；".join(duties),
            "evidence": "；".join(duties),
            "detail_url": "",
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
        }
        for name, duties in ordered.items()
    ]


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
