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
    "rule_id": "2524",
    "page_type": "人物列表完整页",
    "structure_group": "xizang_sport_inline_name_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "page_inline",
    "collector": "static_http",
    "parser": "custom_xizang_sport_inline_name_duty_paragraphs_v1",
    "leader_region_selector": ".xl-atl-plists .TRS_UEDITOR",
    "name_selector": "职务标记前的同段姓名文本",
    "duty_selector": "同段以区体育局开头的剩余文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个姓名职务段",
        "end_anchor": "末个姓名职务段",
        "include_selectors": [".xl-atl-plists .TRS_UEDITOR > p"],
        "exclude_selectors": ["附件下载"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "姓名含不规则排版空格且与职务同段；只以同段明确‘区体育局’职务边界切分，不扫描全页",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".xl-atl-plists .TRS_UEDITOR",
            "name_selector": "p中区体育局标记之前",
            "duty_selector": "p中从区体育局标记开始",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个含区体育局的正文段",
                "end_anchor": "末个含区体育局的正文段",
                "include_selectors": [".xl-atl-plists .TRS_UEDITOR > p"],
                "exclude_selectors": ["空段", "附件区"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文段直接提供姓名和职务",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[\s\u2002-\u200b]+", " ", text)
    return text.strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序，以明确职务前缀切分姓名与原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".xl-atl-plists .TRS_UEDITOR")
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.select(":scope > p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        marker_index = text.find("区体育局")
        if marker_index <= 0:
            continue
        name = re.sub(r"\s+", "", text[:marker_index])
        duty = _clean_text(text[marker_index:])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_xizang_sport_inline_name_duty_paragraphs_v1",
                "selector_summary": ".xl-atl-plists .TRS_UEDITOR逐段；区体育局职务边界",
            }
        )
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
