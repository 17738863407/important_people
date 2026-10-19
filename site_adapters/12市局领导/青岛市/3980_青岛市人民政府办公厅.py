from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3980", "domain": "www.qingdao.gov.cn", "page_type": "机构信息页领导表格",
    "structure_group": "qingdao_department_profile_leader_table", "reuse_scope": "qingdao_government_profile_platform",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_qingdao_profile_leader_table_v1", "leader_region_selector": "#table5",
    "name_selector": "td[rowspan] p", "duty_selector": "tr td:nth-of-type(3)",
    "content_scope": {"include_selectors": ["#table5"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页含职能、内设机构等大量表格，必须限定领导专表及职务标签行",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#table5", "record_selector": "tr:has(td[rowspan])"}},
}


def normalize_text(value: str) -> str:
    """清理表格单元格中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导表首行的姓名、职务标签及相邻值单元格解析。"""
    soup = BeautifulSoup(html, "html.parser")
    table = next((item for item in soup.select("table#table5") if "个人简历" in item.get_text() and "工作分工" in item.get_text()), None)
    if table is None:
        from crawler_core.fetcher import fetch_html_with_strategy

        raw_result = fetch_html_with_strategy(str(page_rule["url"]), strategy="raw_http")
        soup = BeautifulSoup(raw_result.html, "html.parser")
        table = next((item for item in soup.select("table#table5") if "个人简历" in item.get_text() and "工作分工" in item.get_text()), None)
    rows: list[dict[str, str]] = []
    if table is not None:
        for tr in table.select("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 3 or cells[0].get("rowspan") is None:
                continue
            name = normalize_text(cells[0].get_text(" ", strip=True))
            label = normalize_text(cells[1].get_text(" ", strip=True))
            duty = normalize_text(cells[2].get_text(" ", strip=True))
            if label != "职务" or not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
                continue
            rows.append({
                "name": name, "duty": duty, "evidence": duty, "detail_url": "",
                "parser": str(page_rule.get("parser", "")), "selector_summary": "#table5中含rowspan姓名的职务标签行",
            })
    if not rows:
        raise RuntimeError("领导专表未解析出有效人物")
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
