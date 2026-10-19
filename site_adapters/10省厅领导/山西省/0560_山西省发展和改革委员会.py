from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩HTML中的全角空格、换行和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按左侧领导列表顺序拆分姓名、原始职务和真实个人页链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("a.list-aside_submenu[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        marker = "省发改委"
        if marker not in text:
            continue
        name_part, duty_part = text.split(marker, 1)
        name = re.sub(r"\s+", "", name_part)
        evidence = clean_text(marker + duty_part)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        rows.append({"name": name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_fgw_aside_leaders_v2",
                     "selector_summary": "leader=a.list-aside_submenu[href]；name=text-before-省发改委；duty=text-from-省发改委；detail=href"})
    return rows


PAGE_RULE = {
    "rule_id": "0560", "page_type": "人物列表完整页", "structure_group": "shanxi_fgw_aside_leaders", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "browser_fallback", "parser": "page_inline_shanxi_fgw_aside_leaders_v2",
    "leader_region_selector": "a.list-aside_submenu[href]", "name_selector": "text before 省发改委", "duty_selector": "text from 省发改委", "detail_link_selector": "a.list-aside_submenu[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["a.list-aside_submenu[href]"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_only", "detail_collector_type": "online", "detail_link_selector": "a.list-aside_submenu[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "HTTP响应含about:blank脚本跳转，online需自动进入无头浏览器；入口本人链接等于依据链接须置空", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "a.list-aside_submenu[href]", "name_selector": "text before 省发改委", "duty_selector": "text from 省发改委", "detail_link_selector": "a.list-aside_submenu[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["a.list-aside_submenu[href]"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "浏览器DOM中的领导侧栏已提供姓名、职务及个人页链接"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
