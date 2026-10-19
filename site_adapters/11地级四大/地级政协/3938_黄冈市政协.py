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
    "rule_id": "3938",
    "domain": "www.hgzx.gov.cn",
    "page_type": "分组人物目录",
    "structure_group": "huanggang_cppcc_zxld_groups_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_huanggang_cppcc_zxld_groups_v1",
    "leader_region_selector": ".container .zxld",
    "name_selector": "ul li p a[href]",
    "duty_selector": ":scope > h3",
    "detail_link_selector": "ul li p a[href]",
    "content_scope": {"include_selectors": [".container .zxld"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页头下拉菜单含重复领导目录且链接编号与正文不同，必须只取正文.zxld",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".container .zxld",
            "group_selector": ":scope > .zxld_list",
            "duty_selector": ":scope > h3",
            "name_selector": "ul li p a[href]",
        },
        "api": {"enabled": False, "reason": "静态正文已明确列出职务分组、姓名和详情链接"},
    },
}


def normalize_text(value: str) -> str:
    """清理目录字段中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按政协领导正文分组顺序提取姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".container .zxld")
    if region is None:
        raise RuntimeError("未找到政协领导正文 .container .zxld")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in region.find_all("div", class_="zxld_list", recursive=False):
        heading = group.find("h3", recursive=False)
        duty = normalize_text(heading.get_text(" ", strip=True) if heading else "")
        if duty not in {"主席", "副主席", "秘书长"}:
            continue
        for link in group.select("ul li p a[href]"):
            name = normalize_text(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(final_url or str(page_rule.get("url", "")), str(link.get("href", ""))),
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".container .zxld直属职务组；ul li p人物链接",
                }
            )
    if not rows:
        raise RuntimeError("政协领导正文未解析出有效人物")
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
