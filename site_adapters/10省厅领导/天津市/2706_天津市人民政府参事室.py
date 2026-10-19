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
    "rule_id": "2706",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_counsellor_single_text_line",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_tianjin_counsellor_single_text_line_v1",
    "leader_region_selector": ".trs_editor_view",
    "name_selector": ".trs_editor_view span文本首段",
    "duty_selector": ".trs_editor_view span文本姓名后部分",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []},
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "源文件标记图片承载，但当前页面领导信息为可见HTML文本；页面其他图片均属模板资源，不启用OCR",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".trs_editor_view",
            "name_selector": "span文本首段",
            "duty_selector": "span文本姓名后部分",
            "detail_link_selector": "",
            "content_scope": {"start_anchor": "领导信息", "end_anchor": "", "include_selectors": [".trs_editor_view"], "exclude_selectors": []},
        },
        "api": {"enabled": False, "reason": "当前静态HTML正文唯一文本行直接包含姓名和职务"},
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ").replace("\u2002", " ")
    return " ".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从正文唯一非空文本行动态切分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".trs_editor_view")
    lines = [_clean_text(node.get_text(" ", strip=True)) for node in scope.select("span")] if scope else []
    rows: list[dict[str, str]] = []
    for line in lines:
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+)", line)
        if not match:
            continue
        duty = _clean_text(match.group("duty"))
        rows.append({"name": match.group("name"), "duty": duty, "detail_url": "", "evidence": duty,
                     "parser": "custom_tianjin_counsellor_single_text_line_v1",
                     "selector_summary": ".trs_editor_view span可见文本；首段姓名、后续职务"})
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
