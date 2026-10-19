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
    "rule_id": "2300",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_justice_titled_leader_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_justice_titled_leader_links_v1",
    "leader_region_selector": ".right_content ul.listli > li > a[title][href]",
    "name_selector": "title末尾姓名",
    "duty_selector": "title中姓名之前的原始职务",
    "detail_link_selector": ".right_content ul.listli > li > a[title][href]",
    "content_scope": {
        "start_anchor": "负责人简介",
        "end_anchor": "",
        "include_selectors": [".right_content ul.listli"],
        "exclude_selectors": [".listtime", "header", "footer", "nav"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_link_from_list_item",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".right_content ul.listli > li > a[title][href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "列表末条含隐藏发布日期，页面其余区域有大量导航链接；仅使用负责人列表直属标题链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_titled_leader_links",
    "locator": {
        "css": {
            "leader_region_selector": ".right_content ul.listli > li > a[title][href]",
            "name_selector": "last_space_delimited_token",
            "duty_selector": "title_before_name",
            "detail_link_selector": "same_anchor_href",
        },
        "api": {
            "enabled": False,
            "reason": "静态负责人列表已直接提供职务、姓名和独立简介链接",
        },
        "migration": {
            "source": "legacy_regex_over_all_page_anchors",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")


def clean_text(text: str) -> str:
    """压缩HTML排版空白，不改变网页文字语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", text or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按负责人列表顺序拆分标题中的职务和姓名。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for anchor in soup.select(page_rule["leader_region_selector"]):
        title = clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
        parts = title.rsplit(" ", 1)
        if len(parts) != 2:
            continue
        evidence, name = parts[0].strip(), re.sub(r"\s+", "", parts[1])
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if NAME_PATTERN.fullmatch(name) is None or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "source_text": title,
                "method": page_rule["parser"],
                "note": "strategy=custom_parse_page；scope=right_content_listli；name=title_last_token；duty=title_prefix；detail=same_anchor_href",
            }
        )
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
