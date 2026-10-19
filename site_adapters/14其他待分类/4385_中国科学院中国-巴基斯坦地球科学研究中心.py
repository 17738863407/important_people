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
    "rule_id": "4385",
    "page_type": "联合中心主任致辞页",
    "structure_group": "cpjrc_director_message",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_cpjrc_director_message_v1",
    "leader_region_selector": ".rich-text .trs_editor_view",
    "name_selector": ".rich-text .trs_editor_view p strong",
    "duty_selector": ".rich-text .trs_editor_view p strong",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".rich-text .trs_editor_view"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文包含大量致辞内容，仅取相邻加粗姓名和主任职务段落",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验主任姓名与完整机构职务为相邻加粗段落",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".rich-text .trs_editor_view", "name_selector": ".rich-text .trs_editor_view p strong", "duty_selector": ".rich-text .trs_editor_view p strong", "detail_link_selector": "", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".rich-text .trs_editor_view"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "主任姓名和职务直接呈现在致辞页HTML中"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2002\u3000]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".rich-text .trs_editor_view")
    if root is None:
        return []
    strong_texts = [clean_text(node.get_text(" ", strip=True)) for node in root.select("p strong")]
    strong_texts = [text for text in strong_texts if text]
    for index in range(len(strong_texts) - 1):
        name, duty = strong_texts[index], strong_texts[index + 1]
        if re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) and "主任" in duty:
            return [{"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": str(page_rule.get("parser", "")), "selector_summary": ".rich-text相邻加粗姓名和主任职务段落"}]
    return []


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
