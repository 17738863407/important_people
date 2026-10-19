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


PAGE_RULE = {
    "rule_id": "0226",
    "page_type": "人物列表完整页",
    "structure_group": "chinapost_leader_cells_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "div.folder-cont td:has(strong)",
    "name_selector": "p strong",
    "duty_selector": "姓名strong后的同一p文本",
    "detail_link_selector": "姓名strong的直属a[href]父节点",
    "detail_strategy": {"required": False, "mode": "list_links"},
    "risk_flag": "同一人物的多项职务以空格或br排版；仅部分姓名存在独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """只清理网页排版空白，不改写职务语义。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导成员单元格顺序提取姓名、原始职务和可验证详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[PersonRecord] = []
    for cell in soup.select("div.folder-cont td"):
        name_node = cell.select_one("p strong")
        if name_node is None:
            continue
        paragraph = name_node.find_parent("p")
        if paragraph is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        fields = [_clean_text(value) for value in paragraph.stripped_strings]
        duty = _clean_text(" ".join(value for value in fields if value and value != name))
        if not name or not duty:
            continue
        parent_link = name_node.parent if name_node.parent and name_node.parent.name == "a" else None
        href = str(parent_link.get("href") or "") if parent_link is not None else ""
        detail_url = urljoin(final_url, href) if href else ""
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="folder-cont人物td内p strong及其后文本",
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
