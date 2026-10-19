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
    "rule_id": "2984",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_health_leader_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_health_leader_paragraphs_v1",
    "leader_region_selector": ".trs_editor_view",
    "name_selector": "直属p中职务字段前文本",
    "duty_selector": "直属p中天津市卫生健康委员会起始文本",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导基本信息", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "姓名内部可能含多个排版空格；仅解析正文非空人物段落，不扫描发布日期、来源、分享和页脚",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".trs_editor_view > p", "name_selector": "职务字段前文本", "duty_selector": "天津市卫生健康委员会起始文本", "detail_link_selector": "", "content_scope": {"start_anchor": "领导基本信息", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []}},
        "api": {"enabled": False, "reason": "当前静态HTML正文7个非空段落直接包含姓名和完整职务"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ").replace("\u2002", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落原序，以职务字段起始文本切分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".trs_editor_view")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in scope.select(":scope > p") if scope else []:
        line = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>.+?)\s*(?P<duty>天津市卫生健康委员会.+)", line)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty,
                     "parser": "custom_tianjin_health_leader_paragraphs_v1",
                     "selector_summary": ".trs_editor_view直属非空p；职务字段前姓名"})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
