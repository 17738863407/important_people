from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4420",
    "page_type": "人物卡片职务姓名分行页",
    "structure_group": "qinghai_jcy_mol_contents_card_v1",
    "reuse_scope": "same_template",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "qinghai_jcy_mol_contents_card_v1",
    "leader_region_selector": ".leader_L .mol_contents",
    "name_selector": ".mol_contents_row .mol_contents_L > span",
    "duty_selector": ".mol_contents_row .mol_contents_L",
    "detail_link_selector": ".mol_contents_row .mol_contents_r a.btnMore[href]",
    "content_scope": {
        "include_selectors": [".leader_L .mol_contents"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_link_only",
        "max_detail_links": 50,
    },
    "risk_flag": "职务与姓名同栏且部分职务带纯句末标点；页面域名与其他青海检察子站不同",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact(value: str) -> str:
    """清除页面排版空白和职务字段末尾的纯句末标点。"""
    return re.sub(r"[\s\u200b\u3000\xa0]+", "", value).strip("：:。")


def _direct_text(node: Tag) -> str:
    """读取左栏姓名节点之外的直属文本，避免把姓名并入职务。"""
    return _compact(" ".join(str(part) for part in node.find_all(string=True, recursive=False)))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐卡片提取左栏职务、姓名及右栏独立详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader_L .mol_contents")
    if region is None:
        return []
    rows: list[PersonRecord] = []
    for card in region.select(":scope > .mol_contents_row"):
        left = card.select_one(":scope > .mol_contents_L")
        name_node = left.select_one(":scope > span") if left is not None else None
        if left is None or name_node is None:
            continue
        name = _compact(name_node.get_text(" ", strip=True))
        duty = _direct_text(left)
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
            continue
        detail_node = card.select_one(":scope > .mol_contents_r a.btnMore[href]")
        detail_url = ""
        if detail_node is not None:
            href = str(detail_node.get("href", "")).strip()
            if href and not href.lower().startswith(("javascript:", "mailto:")) and href != "#":
                detail_url = urljoin(final_url, href)
        rows.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".leader_L .mol_contents直属人物卡片的左栏职务/姓名与右栏详情链接",
            )
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
