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
    "rule_id": "3661", "page_type": "双栏职务姓名表格页",
    "structure_group": "hnu_current_leader_tables_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "hnu_current_leader_tables_v1",
    "leader_region_selector": "#vsb_content", "name_selector": "table tr td + td a[href]",
    "duty_selector": "table tr td:first-child", "detail_link_selector": "table tr td + td a[href]",
    "content_scope": {"include_selectors": ["#vsb_content"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_link_only", "max_detail_links": 50},
    "risk_flag": "党委与行政双表重复人物；党委常委单元格含展示顺序附注",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """删除排版空白及明确的展示顺序附注。"""
    value = re.sub(r"[（(]\s*按姓氏笔画排序\s*[）)]", "", value)
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按两张表格的行顺序提取并聚合同一人物的多项职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#vsb_content")
    if region is None:
        return []
    people: dict[str, dict[str, object]] = {}
    for row in region.select("table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        duty = _clean_text(cells[0].get_text(" ", strip=True))
        if not duty:
            continue
        for anchor in cells[1].select("a[href]"):
            name = _clean_text(anchor.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                continue
            person = people.setdefault(name, {"duties": [], "detail_url": urljoin(final_url, anchor["href"])})
            if duty not in person["duties"]:
                person["duties"].append(duty)
    return [
        PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(person["duties"]), detail_url=person["detail_url"],
            evidence="；".join(person["duties"]), confidence="high", parser=page_rule["parser"],
            selector_summary="#vsb_content table tr第一列职务与第二列人物链接",
        ) for name, person in people.items()
    ]


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
