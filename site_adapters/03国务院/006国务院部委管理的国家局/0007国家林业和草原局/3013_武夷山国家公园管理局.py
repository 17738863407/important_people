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
    "rule_id": "3013", "page_type": "人物列表完整页", "structure_group": "wuyishan_leader_list_name_duty_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_wuyishan_leader_list_name_duty_v1",
    "leader_region_selector": ".ldzc li", "name_selector": ".ld_name a[href]", "duty_selector": ".ld_zw", "detail_link_selector": ".ld_name a[href]",
    "content_scope": {"start_anchor": "领导班子", "end_anchor": "", "include_selectors": [".ldzc"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "direct_links", "detail_collector_type": "static_http", "detail_link_selector": ".ld_name a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "旧脚本从业务源字段拼接详情链接并返回旧行字段；现以最终入口URL和同人物锚点动态解析", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_leader_list_direct_fields",
    "locator": {"css": {"leader_region_selector": ".ldzc li", "name_selector": ".ld_name a[href]", "duty_selector": ".ld_zw", "detail_link_selector": ".ld_name a[href]"}, "api": {"enabled": False, "reason": "原始HTML直接提供领导姓名、职务和详情链接"}, "migration": {"source": "legacy_business_source_and_old_row_shape_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one(".ld_name a[href]")
        duty_node = item.select_one(".ld_zw")
        name = clean_text(str(link.get("title") or "") if link else "") or clean_text(link.get_text(" ", strip=True) if link else "")
        name = name.replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, str(link.get("href") or "").strip()), "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=ldzc_li；fields=ld_name_ld_zw；order=dom"})
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
