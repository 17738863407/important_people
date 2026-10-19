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
    "rule_id": "0482",
    "page_type": "人物列表完整页",
    "structure_group": "xizang_drc_work_division_titles",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "page_inline",
    "collector": "static_http",
    "parser": "custom_xizang_drc_work_division_titles_v1",
    "leader_region_selector": ".xl-atl-plists .view.trs_word",
    "name_selector": "正文标题段正则：姓名（职务）",
    "duty_selector": "正文标题段中文括号内职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个姓名（职务）标题段",
        "end_anchor": "末个姓名（职务）标题段",
        "include_selectors": [".xl-atl-plists .view.trs_word > p"],
        "exclude_selectors": ["主持", "负责", "分管"],
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
    "risk_flag": "正文标题段后紧跟主持、负责、分管内容；只接受整段完全匹配姓名（职务）的标题，禁止扫描职责段",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".xl-atl-plists .view.trs_word",
            "name_selector": "p整段正则姓名组",
            "duty_selector": "p整段正则中文括号职务组",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个匹配标题段",
                "end_anchor": "末个匹配标题段",
                "include_selectors": [".xl-atl-plists .view.trs_word > p"],
                "exclude_selectors": ["职责段", "分工段"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文以独立标题段直接提供姓名与职务",
        },
    },
}


LEADER_TITLE_RE = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,8})（(?P<duty>[^（）]{2,80})）$")


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u2002", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文DOM顺序解析完全匹配“姓名（职务）”的标题段。"""
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".xl-atl-plists .view.trs_word")
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for paragraph in content.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = LEADER_TITLE_RE.fullmatch(text)
        if match is None:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                # 仅导出括号中的职务原文；标题段中的姓名不属于职务证据。
                "evidence": duty,
                "parser": "custom_xizang_drc_work_division_titles_v1",
                "selector_summary": ".xl-atl-plists .view.trs_word正文；整段姓名（职务）正则",
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
