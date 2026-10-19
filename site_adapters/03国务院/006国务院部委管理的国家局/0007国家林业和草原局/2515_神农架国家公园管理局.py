from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2515", "page_type": "人物列表完整页", "structure_group": "shennongjia_leader_text_links_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_shennongjia_leader_text_links_v1",
    "leader_region_selector": "a[href*='/zwgk/jgsz/ldzc/'], a[href^='./'][href$='.shtml']", "name_selector": "text_prefix", "duty_selector": "text_between_name_and_work_division", "detail_link_selector": "a[href*='/zwgk/jgsz/ldzc/'], a[href^='./'][href$='.shtml']",
    "content_scope": {"start_anchor": "领导之窗", "end_anchor": "", "include_selectors": ["a[href^='./'][href$='.shtml']"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "direct_links", "detail_collector_type": "static_http", "detail_link_selector": "a[href*='/zwgk/jgsz/ldzc/'], a[href^='./'][href$='.shtml']", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "每人有同URL图片空锚点和人物文本锚点；文本锚点在职务后连接较长分工，必须以分工边界截断", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_text_link_work_division_boundary",
    "locator": {"css": {"leader_region_selector": "a[href*='/zwgk/jgsz/ldzc/'], a[href^='./'][href$='.shtml']", "text_pattern": "姓名 职务 分工 职责"}, "api": {"enabled": False, "reason": "原始HTML直接提供人物文本锚点和详情链接"}, "migration": {"source": "legacy_business_source_and_offline_claim_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(?P<name>[\u4e00-\u9fff·]{2,8})\s+(?P<duty>.+?)\s+分工(?:\s|$)")
    for anchor in soup.select(page_rule["leader_region_selector"]):
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if not re.fullmatch(r"/zwgk/jgsz/ldzc/\d+/t\d+\.shtml", urlparse(detail_url).path):
            continue
        match = pattern.match(clean_text(anchor.get_text(" ", strip=True)))
        if match is None:
            continue
        name = match.group("name")
        duty = clean_text(match.group("duty"))
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_text_links；boundary=work_division；order=dom"})
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
