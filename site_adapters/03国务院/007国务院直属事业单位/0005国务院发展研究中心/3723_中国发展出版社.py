from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3723", "page_type": "首页领导列表", "structure_group": "develpress_home_leaders_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_develpress_home_leaders_v1",
    "leader_region_selector": ".news .c_left2", "name_selector": ".news .c_left2 a.workname", "duty_selector": ".news .c_left2 a.workname", "detail_link_selector": ".news .c_left2 a.workname[href]",
    "content_scope": {"start_anchor": "单位领导", "end_anchor": "热点新闻", "include_selectors": [".news .c_left2"], "exclude_selectors": ["script", "style"]}, "detail_strategy": {"required": False, "mode": "direct_links", "detail_link_selector": ".news .c_left2 a.workname[href]", "max_detail_links": 20},
    "risk_flag": "首页同类workname用于其他栏目，必须限定.news中的单位领导左栏；姓名与职务合写在括号内", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_name_role_links",
    "locator": {"css": {"container_selector": ".news .c_left2", "row_selector": "a.workname[href]"}, "api": {"enabled": False, "reason": "原始HTML单位领导栏直接提供姓名、职务与独立链接"}, "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = next((node for node in soup.select(".news .c_left2") if "单位领导" in clean_text(node.get_text(" ", strip=True))), None)
    if container is None:
        return []
    rows: list[dict[str, str]] = []
    for anchor in container.select("a.workname[href]"):
        text = clean_text(anchor.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})（(?P<duty>[^）]+)）", text)
        if match is None:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        rows.append({"name": match.group("name"), "duty": match.group("duty"), "detail_url": detail_url, "source_text": match.group("duty"), "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=unit_leaders；order=anchor_dom"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
