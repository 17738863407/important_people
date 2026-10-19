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
    "rule_id": "3983", "domain": "www.picc.com.cn", "page_type": "集团领导简介卡片",
    "structure_group": "picc_group_leader_profiles", "reuse_scope": "picc_group_leaders",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_picc_group_leader_profiles_v1", "leader_region_selector": ".renbjt-leader-ul",
    "name_selector": ".renbjt-leader-li .leader-name", "duty_selector": ".renbjt-leader-li .leader-text",
    "content_scope": {"include_selectors": [".renbjt-leader-ul"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "简介混有性别学历和其他身份，只能在单张人物卡内提取完整现任句",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"record_selector": ".renbjt-leader-ul > .renbjt-leader-li", "name_selector": ".leader-name", "bio_selector": ".leader-text"}},
}


def normalize_text(value: str) -> str:
    """清理简介中的纯排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在每张人物卡内定位“现任”句并去除句首标签和句末标点。"""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one(".renbjt-leader-ul > .renbjt-leader-li"):
        from crawler_core.fetcher import fetch_html_with_strategy

        raw_result = fetch_html_with_strategy(str(page_rule["url"]), strategy="raw_http")
        soup = BeautifulSoup(raw_result.html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".renbjt-leader-ul > .renbjt-leader-li"):
        name_node = card.select_one(".leader-name")
        bio_node = card.select_one(".leader-text")
        name = normalize_text(name_node.get_text(" ", strip=True)) if name_node else ""
        bio = normalize_text(bio_node.get_text(" ", strip=True)) if bio_node else ""
        match = re.search(r"现任([^。]+)", bio)
        duty = match.group(1).strip("。；; ") if match else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "parser": str(page_rule.get("parser", "")), "selector_summary": "单张集团领导卡姓名及完整现任句",
        })
    if not rows:
        raise RuntimeError("集团领导简介卡片未解析出有效人物")
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
