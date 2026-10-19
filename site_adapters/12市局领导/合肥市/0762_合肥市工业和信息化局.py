from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0762",
    "page_type": "人物表格页",
    "structure_group": "hefei_public_info_name_duty_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "parser": "hefei_public_info_name_duty_links_v1",
    "leader_region_selector": "table.xxgk-table-list",
    "name_selector": "tbody > tr > td.title-td > a.title[href]",
    "duty_selector": "tbody > tr > td.title-td > a.title[href]",
    "detail_link_selector": "tbody > tr > td.title-td > a.title[href]",
    "detail_strategy": {
        "required": True,
        "mode": "same_row_person_link",
        "max_detail_links": 30,
    },
    "risk_flag": "普通HTTP返回521；人物姓名与职务合并在同一链接文本中",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """合并网页排版空白，保留姓名和职务之间的字段边界。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按当前领导表格行顺序解析合并的姓名、职务和人物详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导表格命中数量异常：{len(regions)}")

    entry_url = final_url or page_rule["url"]
    entry_host = urlsplit(entry_url).netloc.lower()
    records: list[object] = []
    seen_names: set[str] = set()
    for link in regions[0].select(page_rule["name_selector"]):
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u3400-\u9fff·]{2,10}) (.+)", text)
        if not match:
            continue
        name, evidence = match.groups()
        evidence = re.sub(r"[（(]\s*挂职\s*[）)]", "", evidence).strip()
        detail_url = urljoin(entry_url, str(link.get("href") or ""))
        detail_parts = urlsplit(detail_url)
        if detail_parts.netloc.lower() != entry_host:
            continue
        if not re.fullmatch(r"/public/17331/\d+\.html", detail_parts.path):
            continue
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )

    max_detail_links = int(page_rule["detail_strategy"]["max_detail_links"])
    if not records or len(records) > max_detail_links:
        raise RuntimeError(f"人物表格有效行数量异常：{len(records)}")
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
