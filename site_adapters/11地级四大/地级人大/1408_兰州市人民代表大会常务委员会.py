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
    "rule_id": "1408",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_renda_xml_cdata_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "lanzhou_renda_xml_cdata_leader_cards_v1",
    "leader_region_selector": "script[type='text/xml']",
    "name_selector": "td[height='36']",
    "duty_selector": "td[height='36']",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["script[type='text/xml']"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "领导记录位于text/xml脚本的CDATA中，普通DOM选择器不可见",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value).strip()


def _split_duty_name(value: str) -> tuple[str, str]:
    text = _clean_text(value)
    match = re.fullmatch(r"(常委会(?:秘书长|副主任|主任))([\u3400-\u9fff·]{2,15})", text)
    if match is None:
        return "", ""
    return match.group(2), match.group(1)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按recordset原始顺序解析XML脚本内的CDATA人物卡片。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen: set[str] = set()
    for script in soup.select("script[type='text/xml']"):
        raw_xml = script.string or script.get_text()
        if "<recordset>" not in raw_xml:
            continue
        xml_soup = BeautifulSoup(raw_xml, "xml")
        for record in xml_soup.select("recordset > record"):
            fragment = BeautifulSoup(record.get_text(), "html.parser")
            cell = fragment.find("td", attrs={"height": "36"})
            if cell is None:
                continue
            name, duty = _split_duty_name(cell.get_text(" ", strip=True))
            if not name or name in seen:
                continue
            seen.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=duty,
                    detail_url="",
                    evidence=duty,
                    confidence="high",
                    parser=page_rule["parser"],
                    selector_summary="text/xml recordset > record CDATA：td[height='36']",
                )
            )
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
