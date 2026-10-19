from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3944",
    "domain": "www.lfzx.gov.cn",
    "page_type": "职务标题人物卡片",
    "structure_group": "linfen_cppcc_cards_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_linfen_cppcc_cards_v1",
    "leader_region_selector": ".subPageRC",
    "name_selector": ".column6PicText1 > a[href]",
    "duty_selector": "span",
    "detail_link_selector": ".column6PicText1 > a[href]",
    "content_scope": {"include_selectors": [".subPageRC"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文使用不规范tr/td标记且头像和姓名各有链接，必须按元素顺序只取文字链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".subPageRC",
            "duty_selector": "span",
            "name_selector": ".column6PicText1 > a[href]",
        },
        "api": {"enabled": False, "reason": "静态正文已含职务标题、姓名和人物详情链接"},
    },
}


def normalize_text(value: str) -> str:
    """清理卡片字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文元素顺序把职务标题应用到随后的人物文字链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".subPageRC")
    if region is None:
        raise RuntimeError("未找到政协领导正文 .subPageRC")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    current_duty = ""
    for node in region.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name == "span":
            label = normalize_text(node.get_text(" ", strip=True))
            if label in {"主席", "副主席", "秘书长"}:
                current_duty = label
            continue
        if node.name != "a" or node.parent is None or "column6PicText1" not in node.parent.get("class", []):
            continue
        name = normalize_text(node.get_text(" ", strip=True))
        if not current_duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": current_duty,
                "evidence": current_duty,
                "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(node.get("href", ""))),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".subPageRC元素顺序；职务span + column6PicText1姓名链接",
            }
        )
    if not rows:
        raise RuntimeError("政协领导正文未解析出有效人物卡片")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
