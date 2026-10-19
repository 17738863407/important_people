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


PAGE_RULE = {
    "rule_id": "2862",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_culture_duty_colon_name_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_culture_duty_colon_name_links_v1",
    "leader_region_selector": "ul.list_right_bar_zjdc > li a[href]",
    "name_selector": "冒号后姓名",
    "duty_selector": "冒号前原始职务",
    "detail_link_selector": "ul.list_right_bar_zjdc > li a[href]",
    "content_scope": {"start_anchor": "领导简介", "end_anchor": "", "include_selectors": ["ul.list_right_bar_zjdc"], "exclude_selectors": [".date", "header", "footer"]},
    "detail_strategy": {"required": False, "mode": "dynamic_link_from_list_item", "detail_collector_type": "static_http", "detail_link_selector": "ul.list_right_bar_zjdc > li a[href]", "detail_parser": "", "detail_name_selector": "", "detail_duty_selector": "", "detail_content_selector": "", "max_detail_links": 20},
    "risk_flag": "页面导航与页脚链接较多；仅解析领导简介列表内职务冒号姓名链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_duty_colon_name_links",
    "locator": {"css": {"leader_region_selector": "ul.list_right_bar_zjdc > li a[href]", "name_selector": "text_after_colon", "duty_selector": "text_before_colon", "detail_link_selector": "same_anchor_href"}, "api": {"enabled": False, "reason": "静态领导简介列表直接提供职务、姓名和详情链接"}, "migration": {"source": "legacy_all_page_anchor_regex", "verified_status": "verified_current_online", "behavior_changed": True}},
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")


def clean_text(text: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导简介列表顺序拆分职务、姓名和详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select(page_rule["leader_region_selector"]):
        text = clean_text(anchor.get_text(" ", strip=True)).lstrip("> ")
        separator = "：" if "：" in text else ":" if ":" in text else ""
        if not separator:
            continue
        evidence, name = [part.strip() for part in text.split(separator, 1)]
        if NAME_PATTERN.fullmatch(name) is None or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "detail_url": urljoin(final_url, str(anchor.get("href") or "").strip()), "source_text": evidence, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=leader_intro_list；name=after_colon；duty=before_colon；detail=same_anchor_href"})
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
