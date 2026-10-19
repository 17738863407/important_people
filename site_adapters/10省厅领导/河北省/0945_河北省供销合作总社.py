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
    "rule_id": "0945",
    "page_type": "人物列表完整页",
    "structure_group": "hebcoop_leader_division_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebcoop_leader_division_paragraphs_v1",
    "leader_region_selector": ".listbox .right .layout1",
    "name_selector": "p文本开头至中文括号",
    "duty_selector": "p文本中文括号内",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "省供销合作总社领导分工",
        "end_anchor": "河北省供销合作总社办公室",
        "include_selectors": [".listbox .right .layout1"],
        "exclude_selectors": [],
    },
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
    "risk_flag": "历史脚本标记图片承载并依赖快照；当前权威入口页已改为可见HTML领导分工段落",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".listbox .right .layout1",
            "name_selector": "p文本开头至中文括号",
            "duty_selector": "p文本中文括号内",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "省供销合作总社领导分工",
                "end_anchor": "河北省供销合作总社办公室",
                "include_selectors": [".listbox .right .layout1"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML正文直接包含姓名和原始职务"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序提取“姓名（职务）”，忽略后续分工说明。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".listbox .right .layout1")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in scope.select("p") if scope else []:
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·\s]{2,8})[（(](?P<duty>[^）)]+)[）)]", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = _clean_text(match.group("duty"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_hebcoop_leader_division_paragraphs_v1",
                "selector_summary": ".listbox .right .layout1 p；姓名（原始职务）",
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
