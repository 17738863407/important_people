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
    "rule_id": "1226",
    "page_type": "人物列表完整页",
    "structure_group": "xm_transport_leader_table_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_transport_leader_table_v2",
    "leader_region_selector": "div.gl_nr table.ldftdbk",
    "name_selector": "td.ldbziwzys.tb a[href]",
    "duty_selector": "tr中的第三个td",
    "detail_link_selector": "td.ldbziwzys.tb a[href]",
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "整页含其他表格和冒号文本；只解析领导表格中姓名链接与同一行第三格职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导表格行顺序提取姓名、原始职务和人物链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.select(page_rule["leader_region_selector"])
    if not tables:
        raise RuntimeError("未找到领导班子表格 div.gl_nr table.ldftdbk")
    records: list[object] = []
    seen: set[str] = set()
    for row in soup.select(f'{page_rule["leader_region_selector"]} tr'):
        cells = row.select("td")
        name_link = row.select_one(page_rule["name_selector"])
        if len(cells) < 3 or name_link is None:
            continue
        name = clean_text(name_link.get_text(" ", strip=True)).rstrip("：:").strip()
        evidence = clean_text(cells[2].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("领导表格行缺少可核对的姓名或职务")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=urljoin(page_rule["url"], str(name_link.get("href") or "")),
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导班子表格中未提取到人物")
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
