from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3599", "domain": "www.ndrctc.org.cn", "page_type": "现任领导文本段落",
    "structure_group": "ndrctc_article_colon_rows_2026", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "duty_colon_name_paragraphs",
    "collector": "static_http", "parser": "page_ndrctc_current_leaders_v1",
    "leader_region_selector": ".article_content", "name_selector": ".article_content p",
    "duty_selector": ".article_content p", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "verified_article_body_only", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(text: str) -> str:
    """删除纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从限定正文段落按“职务：姓名”结构提取。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".article_content")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    for paragraph in region.select(":scope > p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>[^：:]{2,30})[：:](?P<name>[\u4e00-\u9fff·]{2,4})", text)
        if match is None:
            continue
        duty, name = match.group("duty"), match.group("name")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                     "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "strategy=custom_parse_page；region=.article_content；row=p；format=职务：姓名"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
