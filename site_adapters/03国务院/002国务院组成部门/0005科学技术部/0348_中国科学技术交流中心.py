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
    "rule_id": "0348", "page_type": "人物列表完整页", "structure_group": "cstec_leader_picture_lists_v2", "reuse_scope": "single_page", "load_mode": "动态DOM渲染", "fetch_mode": "online", "force_browser": True, "extract_mode": "list_direct", "collector": "browser_dom", "parser": "page_inline_cstec_leader_picture_lists_v2",
    "leader_region_selector": "#thpic li, #fthpic li", "name_selector": "a > div:first-of-type", "duty_selector": "a > div:nth-of-type(2)", "detail_link_selector": "a[href]",
    "content_scope": {"start_anchor": "中心领导", "end_anchor": "机构设置", "include_selectors": ["#thpic", "#fthpic"], "exclude_selectors": ["footer", "script", "style", "[hidden]", "[style*='display:none']"]},
    "detail_strategy": {"required": False, "mode": "list_links_only", "detail_collector_type": "browser_dom", "detail_link_selector": "#thpic li a[href], #fthpic li a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "普通HTTPS证书链异常且原始HTML无领导列表；当前渲染DOM中心领导主副图片区块为权威来源", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_leader_picture_lists",
    "locator": {"css": {"leader_region_selector": "#thpic li, #fthpic li", "name_selector": "a > div:first-of-type", "duty_selector": "a > div:nth-of-type(2)", "detail_link_selector": "a[href]"}, "api": {"enabled": False, "reason": "当前渲染DOM中心领导图片区块直接提供姓名、职务和独立详情链接"}, "migration": {"source": "legacy_offline_business_source_and_entry_detail_removed", "verified_status": "verified_current_browser_dom", "behavior_changed": True}},
}

def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()

def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one("a[href]")
        texts = [compact(node.get_text(" ", strip=True)) for node in item.select("a > div")]
        texts = [text for text in texts if text]
        if len(texts) < 2 or link is None or not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", texts[0]):
            continue
        rows.append({"name": texts[0], "duty": texts[1], "detail_url": urljoin(final_url, link.get("href", "")), "source_text": texts[1], "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=thpic_fthpic；name=div1；duty=div2；detail=href；order=primary_then_secondary"})
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")

if __name__ == "__main__":
    main()
