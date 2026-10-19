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
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按职务分组卡片提取，姓名标题中的独立挂职标记仅用于识别。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".innerCon2")
    if region is None:
        return []
    source_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    for group in region.select(":scope > .section"):
        duty_node = group.select_one(":scope > span")
        duty = clean_text(duty_node.get_text(" ", strip=True)).replace(" ", "").rstrip("：:") if duty_node else ""
        for link in group.select("ul > li > a[href]"):
            raw_name = clean_text(str(link.get("title") or link.get_text(" ", strip=True))).replace(" ", "")
            name = re.sub(r"[（(]挂职[）)]$", "", raw_name)
            if duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                rows.append({"name": name, "duty": "", "evidence": duty,
                             "detail_url": urljoin(source_url, str(link.get("href") or "")),
                             "confidence": "high", "parser": "page_inline_jiangmen_government_groups_v1"})
    return rows


PAGE_RULE = {
    "rule_id": "3836", "page_type": "职务分组卡片页", "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright", "_fetch_mode_override": True, "extract_mode": "list_direct",
    "parser": "page_inline_jiangmen_government_groups_v1", "leader_region_selector": ".innerCon2",
    "name_selector": ".section li a[title]", "duty_selector": ".section > span",
    "detail_link_selector": ".section li a[href]", "locator_strategy": "custom_parse_page",
    "risk_flag": "HTTP直连被防护拦截，需Playwright渲染", "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
