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
    "rule_id": "1808", "page_type": "多人物详情合并页", "structure_group": "mzywfyj_news_content_colon_rows_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "merged_detail_page", "collector": "static_http", "parser": "page_inline_mzywfyj_news_content_colon_rows_v1",
    "leader_region_selector": ".news_content p", "name_selector": "paragraph_colon_suffix", "duty_selector": "paragraph_colon_prefix", "detail_link_selector": "",
    "content_scope": {"start_anchor": "现任局领导", "end_anchor": "", "include_selectors": [".news_content"], "exclude_selectors": ["footer", "script", "style"]},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 10},
    "risk_flag": "页脚另有地址和备案冒号文本；只解析news_content人物段落，姓名尾部性别或挂职括注不属于姓名", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_scoped_colon_paragraphs",
    "locator": {"css": {"leader_region_selector": ".news_content p", "row_pattern": "完整职务：姓名及括注"}, "api": {"enabled": False, "reason": "原始HTML正文容器直接提供完整职务与姓名"}, "migration": {"source": "legacy_business_source_personrecord_and_entry_detail_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        text = clean_text(paragraph.get_text(" ", strip=True)).replace("（", "(").replace("）", ")")
        parts = re.split(r"[：:]", text, maxsplit=1)
        if len(parts) != 2:
            continue
        duty = clean_text(parts[0])
        name = re.sub(r"\(.*?\)", "", clean_text(parts[1])).replace(" ", "")
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=news_content；fields=paragraph_colon；order=dom"})
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
