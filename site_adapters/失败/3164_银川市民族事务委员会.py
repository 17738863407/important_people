from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3164",
    "page_type": "人物目录详情页",
    "structure_group": "yinchuan_ethnic_affairs_responsibility_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_ethnic_affairs_responsibility_paragraphs_v2",
    "leader_region_selector": ".zwxxgk_bd",
    "name_selector": "叶级分工段首“姓名同志：”",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".zwxxgk_bd"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "detail_collector_type": "static_http", "detail_link_selector": None, "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 0},
    "risk_flag": "页面仅明确姓名和工作分工，未提供职务字段；保留姓名并让依据说明留空",
    "confidence": "medium",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


NAME_PATTERN = re.compile(r"^([\u4e00-\u9fff·\s]{2,8})同志\s*[:：]")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """压缩正文中的全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """核验工作分工页是否同时公开姓名和可用职务依据。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        if paragraph.select_one("p") is not None:
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = NAME_PATTERN.search(text)
        if match is None:
            continue
        name = "".join(match.group(1).split())
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": "", "evidence": "", "detail_url": "", "parser": str(page_rule.get("parser") or ""), "selector_summary": ".zwxxgk_bd内叶级分工p；段首姓名同志；职责不作为职务依据"})
    if rows:
        return rows
    raise RuntimeError("领导工作分工正文未解析到可验证姓名")


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
