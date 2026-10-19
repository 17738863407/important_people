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
    """清理网页字段中的排版空白。"""
    return re.sub(r"\s+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导班子图片卡片顺序提取“姓名（职务）”。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".c_rcontent ul.img_list > li > a.img_head[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})（([^）]{2,30})）", text)
        if match is None:
            continue
        name, duty = match.group(1), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_qinghai_sports_cards_v2",
                "selector_summary": "leader=.c_rcontent ul.img_list>li>a.img_head[href]；field=姓名（职务）；detail=href",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2784",
    "page_type": "人物列表完整页",
    "structure_group": "qinghai_sports_image_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_qinghai_sports_cards_v2",
    "leader_region_selector": ".c_rcontent ul.img_list > li",
    "name_selector": "a.img_head中括号前姓名",
    "duty_selector": "a.img_head括号内职务",
    "detail_link_selector": "a.img_head[href]",
    "content_scope": {
        "start_anchor": "领导班子",
        "end_anchor": "联系我们",
        "include_selectors": [".c_rcontent ul.img_list"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "raw_http",
        "detail_link_selector": "a.img_head[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "入口页脚本跳转会误入空关键词搜索，必须保留原始HTTP响应",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".c_rcontent ul.img_list > li",
            "name_selector": "a.img_head中括号前姓名",
            "duty_selector": "a.img_head括号内职务",
            "detail_link_selector": "a.img_head[href]",
            "content_scope": {
                "start_anchor": "领导班子",
                "end_anchor": "联系我们",
                "include_selectors": [".c_rcontent ul.img_list"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "原始HTML已提供领导图片卡片、职务和人物链接"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online_raw_http",
            "behavior_changed": True,
        },
    },
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
