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
    "rule_id": "1366", "page_type": "人物列表完整页", "structure_group": "shenyang_science_spaced_heading_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_science_spaced_heading_v2",
    "leader_region_selector": "ul.xxgk_rul .qw-list", "name_selector": ".yangs首个直接子b连续空白前",
    "duty_selector": ".yangs首个直接子b连续空白后", "detail_link_selector": ".qw-list直接子a[href*=bumenlingdao]",
    "detail_strategy": {"required": True, "mode": "list_item_link"},
    "risk_flag": "姓名与职务共处首个b并由连续排版空白分隔；后续p为工作分工，必须排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理字段内部的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按卡片DOM顺序解析连续空白分隔的姓名和原始职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in soup.select("ul.xxgk_rul .qw-list"):
        block = card.select_one(".yangs")
        heading = block.find("b", recursive=False) if block is not None else None
        raw_heading = heading.get_text(" ", strip=True) if heading is not None else ""
        parts = re.split(r"[\s\u2000-\u200b\u3000\xa0]{2,}", raw_heading, maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError("人物卡片姓名与职务分隔异常")
        name = re.sub(r"\s+", "", clean_text(parts[0]))
        evidence = clean_text(parts[1])
        detail_link = card.find("a", href=True, recursive=False)
        href = clean_text(detail_link.get("href", "") if detail_link else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物卡片姓名或职务字段异常")
        if "bumenlingdao/" not in href or not detail_url:
            raise RuntimeError(f"人物详情链接异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物卡片姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到人物卡片")
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
