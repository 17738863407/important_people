from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2234",
    "page_type": "人物列表完整页",
    "structure_group": "sass_xsl_leader_table",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "custom_sass_xsl_leader_table_v1",
    "leader_region_selector": ".text_view.item2 table",
    "name_selector": "tr td:first-child",
    "duty_selector": "tr td:nth-child(2)",
    "detail_link_selector": "tr td:first-child a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".text_view.item2 table"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "browser_dom",
        "detail_link_selector": "tr td:first-child a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "入口为XML，人物表格由浏览器应用XSL后生成；仅解析领导简介分组",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "css",
    "locator": {
        "css": {
            "leader_region_selector": ".text_view.item2 table",
            "name_selector": "tr td:first-child",
            "duty_selector": "tr td:nth-child(2)",
            "detail_link_selector": "tr td:first-child a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".text_view.item2 table"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "入口XML不含人物节点，浏览器应用站点XSL后形成稳定领导表格",
        },
    },
}


def _clean_text(text: str) -> str:
    """清理站点表格中的不换行空格和排版空白。"""
    return re.sub(r"\s+", "", text.replace("\u3000", " "))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析“领导简介”分组内的两列表格，并保留网页原始顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    source_host = urlparse(source_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for tr in soup.select(".text_view.item2 table tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 2:
            continue

        name = _clean_text(cells[0].get_text(" ", strip=True))
        duty = " ".join(cells[1].get_text(" ", strip=True).split())
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        detail_url = ""
        link = cells[0].find("a", href=True)
        if link:
            candidate = urljoin(final_url or source_url, str(link.get("href") or "").strip())
            parsed = urlparse(candidate)
            if parsed.netloc.lower() == source_host and parsed.path.lower().endswith(".aspx"):
                detail_url = candidate

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_sass_xsl_leader_table_v1",
                "selector_summary": ".text_view.item2 table tr；第一列姓名；第二列职务",
            }
        )

    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
