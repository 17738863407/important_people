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
    "rule_id": "3257",
    "page_type": "人物表格页",
    "structure_group": "sichuan_healthcare_leader_cells",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_sichuan_healthcare_leader_cells_v1",
    "leader_region_selector": "#xxgkzn_detail",
    "name_selector": "td[width='148'] a[title]:has(img)",
    "duty_selector": "td[width='148'] > table:first-of-type",
    "detail_link_selector": "td[width='148'] a[title]:has(img)",
    "content_scope": {
        "start_anchor": "机关领导",
        "end_anchor": "",
        "include_selectors": ["#xxgkzn_detail"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "td[width='148'] a[title]:has(img)",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "嵌套表格同时包含职务、头像和姓名；职务限定人物单元格首个直属table",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#xxgkzn_detail",
            "name_selector": "td[width='148'] a[title]:has(img)",
            "duty_selector": "td[width='148'] > table:first-of-type",
            "detail_link_selector": "td[width='148'] a[title]:has(img)",
            "content_scope": {
                "start_anchor": "机关领导",
                "end_anchor": "",
                "include_selectors": ["#xxgkzn_detail"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML人物单元格直接包含职务、姓名和独立人物链接",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理不换行空格和排版空白，不改变职务语义。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析人物单元格，继承入口嵌套表格的原始顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    source_host = urlparse(source_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("#xxgkzn_detail a[title]"):
        if not link.select_one("img"):
            continue
        cell = link.find_parent("td", attrs={"width": "148"})
        tables = cell.find_all("table", recursive=False) if cell else []
        if not tables:
            continue

        name = re.sub(r"\s+", "", str(link.get("title") or ""))
        duty = _clean_text(tables[0].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        detail_url = ""
        candidate = urljoin(final_url or source_url, str(link.get("href") or "").strip())
        parsed = urlparse(candidate)
        real_person_page = bool(
            re.fullmatch(r"/scsybj/nc0104020[1-3]/\d{4}/\d{1,2}/\d{1,2}/[0-9a-f]+\.shtml", parsed.path)
        )
        if parsed.netloc.lower() == source_host and real_person_page:
            detail_url = candidate

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_sichuan_healthcare_leader_cells_v1",
                "selector_summary": "#xxgkzn_detail人物td；头像链接title姓名；首个直属table职务",
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
