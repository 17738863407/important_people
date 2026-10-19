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
    "rule_id": "3958",
    "domain": "gxylzx.gov.cn",
    "page_type": "职务分组人物表格",
    "structure_group": "yulin_cppcc_leader_table",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_yulin_cppcc_table_v1",
    "leader_region_selector": ".gk_content_right table",
    "name_selector": "a[href*='leader_detail.ptl?leaderId=']",
    "duty_selector": "td.ld_mc",
    "detail_link_selector": "a[href*='leader_detail.ptl?leaderId=']",
    "content_scope": {"include_selectors": [".gk_content_right"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "主席头像与姓名共用重复详情链接，须按表格行内非空链接文字去重",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".gk_content_right",
            "group_row_selector": "tr:has(td.ld_mc)",
            "duty_selector": "td.ld_mc",
            "name_selector": "a[href*='leader_detail.ptl?leaderId=']",
        },
        "api": {"enabled": False, "reason": "静态表格已直接包含分组职务、姓名和人物详情链接"},
    },
}


def normalize_text(value: str) -> str:
    """删除姓名和职务中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐表格行读取职务，并对行内有姓名文字的详情链接去重。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".gk_content_right")
    if region is None:
        raise RuntimeError("未找到政协领导内容区域 .gk_content_right")
    rows: list[dict[str, str]] = []
    for group_row in region.select("tr"):
        duty_node = group_row.select_one("td.ld_mc")
        if duty_node is None:
            continue
        duty = normalize_text(duty_node.get_text(" ", strip=True))
        if duty not in {"主席", "副主席", "秘书长"}:
            continue
        seen: set[str] = set()
        for link in group_row.select("a[href*='leader_detail.ptl?leaderId=']"):
            name = normalize_text(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))),
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "领导表格职务行内带姓名文字的人物详情链接",
                }
            )
    if not rows:
        raise RuntimeError("政协领导表格未解析出有效人物")
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
