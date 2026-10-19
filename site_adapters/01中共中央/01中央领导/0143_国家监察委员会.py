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
    "rule_id": "0143", "page_type": "人物列表完整页", "structure_group": "ccdi_national_supervisory_commission_groups_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_direct", "collector": "static_http", "parser": "page_inline_ccdi_national_supervisory_commission_groups_v1",
    "leader_region_selector": ".ldjg h2.tit2, .ldjg .content2", "name_selector": "span.spa4 a, span.spa2 a", "duty_selector": "span.spa1", "detail_link_selector": ".ldjg .content2 a[href]",
    "content_scope": {"start_anchor": "中华人民共和国国家监察委员会", "end_anchor": "", "include_selectors": [".ldjg"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "direct_links", "detail_collector_type": "static_http", "detail_link_selector": ".ldjg .content2 a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 50},
    "risk_flag": "同页先列中央纪委、后列国家监委，必须从国家监委标题开始且只接受主任、副主任两个领导分组，排除末尾独立委员分组", "confidence": "high", "profile_reusable": "", "profile_judgement": "", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_heading_bounded_groups",
    "locator": {"css": {"heading_selector": ".ldjg h2.tit2", "group_selector": ".ldjg .content2", "name_selector": "span.spa4 a, span.spa2 a", "duty_selector": "span.spa1"}, "api": {"enabled": False, "reason": "原始HTML直接提供目标委员会分组、姓名与详情链接"}, "migration": {"source": "legacy_business_source_and_old_row_shape_removed", "verified_status": "verified_current_online", "behavior_changed": True}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(value: str) -> str:
    return re.sub(r"（[^）]+）", "", clean_text(value).replace(" ", ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    heading = next((node for node in soup.select(".ldjg h2.tit2") if "中华人民共和国国家监察委员会" in clean_text(node.get_text(" ", strip=True))), None)
    if heading is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in heading.find_next_siblings():
        if getattr(block, "name", None) == "h2":
            break
        if "content2" not in (block.get("class") or []):
            continue
        duty = "".join(clean_text(node.get_text(" ", strip=True)).replace(" ", "") for node in block.select("span.spa1"))
        if duty not in {"主任", "副主任"}:
            continue
        for anchor in block.select(page_rule["name_selector"]):
            name = clean_name(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": duty, "detail_url": urljoin(final_url, str(anchor.get("href") or "").strip()), "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=national_supervisory_commission_heading；order=group_then_dom"})
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
