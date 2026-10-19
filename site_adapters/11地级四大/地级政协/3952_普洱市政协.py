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
    "rule_id": "3952",
    "domain": "pezx.gov.cn",
    "page_type": "侧栏职务分组人物目录",
    "structure_group": "puer_cppcc_sidebar_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_puer_cppcc_sidebar_v1",
    "leader_region_selector": ".subMenu dl",
    "name_selector": "dd > ul > li > a[href*='id=']",
    "duty_selector": "dd .tableCell",
    "detail_link_selector": "dd > ul > li > a[href*='id=']",
    "content_scope": {"include_selectors": [".subMenu dl"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "右侧正文仅展示当前选中人物，完整名单必须从左侧职务分组目录提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".subMenu dl",
            "group_selector": ":scope > dd",
            "duty_selector": ".tableCell",
            "name_selector": ":scope > ul > li > a[href*='id=']",
        },
        "api": {"enabled": False, "reason": "静态侧栏已包含完整分组名单和独立人物查询链接"},
    },
}


def normalize_text(value: str) -> str:
    """删除字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按侧栏职务分组和人物链接顺序提取完整名单。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".subMenu dl")
    if region is None:
        raise RuntimeError("未找到政协领导侧栏 .subMenu dl")
    rows: list[dict[str, str]] = []
    for group in region.select(":scope > dd"):
        duty_node = group.select_one(".tableCell")
        duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if duty not in {"政协主席", "政协副主席", "秘书长"}:
            continue
        for link in group.select(":scope > ul > li > a[href*='id=']"):
            name = normalize_text(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
                continue
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))),
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".subMenu dl直属dd职务分组内人物查询链接",
                }
            )
    if not rows:
        raise RuntimeError("政协领导侧栏未解析出有效人物")
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
