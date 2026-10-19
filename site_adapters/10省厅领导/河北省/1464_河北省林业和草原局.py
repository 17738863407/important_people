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
    "rule_id": "1464",
    "page_type": "人物列表完整页",
    "structure_group": "hebei_forestry_bold_name_duty",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_hebei_forestry_bold_name_duty_v1",
    "leader_region_selector": ".news-detail-content-box",
    "name_selector": "strong中文括号前文本",
    "duty_selector": "strong中文括号内文本",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "局领导", "end_anchor": "", "include_selectors": [".news-detail-content-box"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "正文strong同时用于其他强调文本；仅接受完整姓名（职务）结构",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".news-detail-content-box", "name_selector": "strong中文括号前文本", "duty_selector": "strong中文括号内文本", "detail_link_selector": "", "content_scope": {"start_anchor": "局领导", "end_anchor": "", "include_selectors": [".news-detail-content-box"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态HTML正文strong直接包含姓名和职务"}},
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文strong顺序提取完整“姓名（职务）”结构。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".news-detail-content-box")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,5})[（(](?P<duty>[^）)]+)[）)]$")
    for strong in scope.select("strong") if scope else []:
        text = _clean_text(strong.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if not match or match.group("name") in seen:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty, "parser": "custom_hebei_forestry_bold_name_duty_v1", "selector_summary": ".news-detail-content-box strong；完整姓名（原始职务），依据说明仅保留括号内职务"})
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
