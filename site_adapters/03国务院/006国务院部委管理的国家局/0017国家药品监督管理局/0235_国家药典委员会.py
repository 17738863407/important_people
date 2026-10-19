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
    "rule_id": "0235", "page_type": "人物列表完整页", "structure_group": "chp_news_detail_leader_paragraphs_v1", "reuse_scope": "single_page", "load_mode": "接口数据加载", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_chp_news_detail_leader_paragraphs_v1",
    "leader_region_selector": ".newsDetail .news-box div.q-pa-md.q-mt-lg > p", "name_selector": ":scope strong", "duty_selector": "paragraph_text_after_name", "detail_link_selector": "",
    "content_scope": {"start_anchor": "委领导", "end_anchor": "友情链接", "include_selectors": [".newsDetail .news-box"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "browser_dom", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 5},
    "risk_flag": "哈希路由入口的HTTP响应不含领导正文，必须浏览器渲染；旧脚本硬编码固定人物结果，现改为正文段落强结构动态抽取", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_rendered_news_detail_paragraphs",
    "locator": {"css": {"leader_region_selector": ".newsDetail .news-box div.q-pa-md.q-mt-lg > p", "name_selector": ":scope strong", "duty_strategy": "remove_name_from_paragraph_text"}, "api": {"enabled": False, "reason": "接口参数未形成可独立复现契约；当前渲染DOM强字段已由在线浏览器核验"}, "migration": {"source": "legacy_fixed_people_and_offline_dependency_removed", "verified_status": "verified_current_online_browser", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    cleaned = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()
    return re.sub(r"\s*([、，：；。])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        name_node = paragraph.select_one("strong")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        line = clean_text(paragraph.get_text(" ", strip=True))
        duty = clean_text(line.replace(clean_text(name_node.get_text(" ", strip=True) if name_node else ""), "", 1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=rendered_news_detail；fields=paragraph_strong_remainder；order=dom"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
