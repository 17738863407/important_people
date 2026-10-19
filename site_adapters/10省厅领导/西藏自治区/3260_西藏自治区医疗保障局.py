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
    "rule_id": "3260",
    "page_type": "人物列表完整页",
    "structure_group": "xizang_healthcare_name_duty_prefix_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "page_inline",
    "collector": "static_http",
    "parser": "custom_xizang_healthcare_name_duty_prefix_v1",
    "leader_region_selector": ".ldzc-intro .TRS_UEDITOR",
    "name_selector": "正文p开头姓名",
    "duty_selector": "正文p开头中文括号内职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个姓名（职务）：段",
        "end_anchor": "末个姓名（职务）：段",
        "include_selectors": [".ldzc-intro .TRS_UEDITOR > p"],
        "exclude_selectors": ["冒号后的主持、负责、分管内容", "交叉分工说明"],
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
    "risk_flag": "职务与职责同段；只提取段首姓名（职务）：结构中括号内原文，冒号后职责全部排除",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldzc-intro .TRS_UEDITOR",
            "name_selector": "> p段首正则姓名",
            "duty_selector": "> p段首中文括号正则职务",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "段首姓名",
                "end_anchor": "紧随中文冒号",
                "include_selectors": [".ldzc-intro .TRS_UEDITOR > p"],
                "exclude_selectors": ["冒号后职责", "末尾协助说明"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前HTTP响应静态直出姓名、职务和职责正文段",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return "".join(text.split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文DOM顺序提取每段开头“姓名（职务）：”中的字段。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".ldzc-intro .TRS_UEDITOR")
    if content is None:
        return []
    pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,6})（(?P<duty>[^（）]{2,80})）：")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.select(":scope > p"):
        text = _clean_text(paragraph.get_text("", strip=True))
        match = pattern.match(text)
        if match is None:
            continue
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_xizang_healthcare_name_duty_prefix_v1",
                "selector_summary": ".ldzc-intro .TRS_UEDITOR逐段；段首姓名（职务）：",
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
