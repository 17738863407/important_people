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
    """压缩列表项排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表顺序以首个“局”字拆分姓名和职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select("#ConList_svxxgk .smallPart_svxxgk li a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        if "局" not in text:
            continue
        name_part, duty_tail = text.split("局", 1)
        name = re.sub(r"\s+", "", name_part)
        evidence = clean_text("局" + duty_tail)
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence or not detail_url or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
                     "confidence": "high", "parser": "page_inline_shanxi_healthcare_security_list_v2",
                     "selector_summary": "leader=#ConList_svxxgk .smallPart_svxxgk li a[href]；name=text-before-first-局；duty=text-from-first-局；detail=href"})
    return rows


PAGE_RULE = {
    "rule_id": "3140", "page_type": "人物列表完整页", "structure_group": "shanxi_healthcare_security_leader_list", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "browser_fallback", "parser": "page_inline_shanxi_healthcare_security_list_v2",
    "leader_region_selector": "#ConList_svxxgk .smallPart_svxxgk li a[href]", "name_selector": "link text before first 局", "duty_selector": "link text from first 局", "detail_link_selector": "#ConList_svxxgk .smallPart_svxxgk li a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["#ConList_svxxgk .smallPart_svxxgk"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "list_link_only", "detail_collector_type": "online", "detail_link_selector": "#ConList_svxxgk .smallPart_svxxgk li a[href]", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "requests被错误脚本跳转至站内搜索404，online需进入无头浏览器；姓名内部含不等数量全角/不换行空格", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#ConList_svxxgk .smallPart_svxxgk li a[href]", "name_selector": "link text before first 局", "duty_selector": "link text from first 局", "detail_link_selector": "#ConList_svxxgk .smallPart_svxxgk li a[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": ["#ConList_svxxgk .smallPart_svxxgk"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "浏览器DOM领导列表已直出姓名、职务和详情页"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
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
