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
    "rule_id": "2405", "page_type": "人物表格页", "structure_group": "shenyang_gov_office_marker_tables_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_gov_office_marker_tables_v2",
    "leader_region_selector": "div#main_text div.view.TRS_UEDITOR直接子table",
    "name_selector": "人物strong中市政府机关锚点之前", "duty_selector": "人物strong中市政府机关锚点起始的原文",
    "detail_link_selector": "当前表格领导个人简历a[href]",
    "detail_strategy": {"required": True, "mode": "list_item_link"},
    "risk_flag": "姓名与职务可能分立或连写；后续工作分工不得混入原始职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白和零宽连接符。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物表格顺序使用职务起始锚点拆分姓名与原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    main = soup.select_one("div#main_text")
    tables = main.select("div.view.TRS_UEDITOR > table") if main is not None else []
    if not tables:
        raise RuntimeError("部门职能正文没有人物表格")
    records: list[object] = []
    seen_names: set[str] = set()
    duty_marker = "市政府机关"
    for table in tables:
        heading = table.select_one("td.font14s p strong")
        heading_text = clean_text(heading.get_text(" ", strip=True) if heading else "")
        marker_index = heading_text.find(duty_marker)
        if marker_index <= 0:
            raise RuntimeError(f"人物表格缺少职务起始锚点：{heading_text}")
        name = re.sub(r"\s+", "", heading_text[:marker_index])
        evidence = heading_text[marker_index:].strip()
        detail_link = table.select_one("td.font14s a[href]")
        href = clean_text(detail_link.get("href", "") if detail_link else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物表格姓名或职务字段异常")
        if not detail_url or detail_url == (final_url or page_rule["url"]):
            raise RuntimeError(f"人物简历链接异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物表格姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
