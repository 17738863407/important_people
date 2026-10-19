from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "0755",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "leader_region_selector": "table",
    "risk_flag": "职务位于简介列完整现任句；分工列不得作为职务，页面没有独立人物详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩表格排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def find_leader_table(soup: BeautifulSoup) -> Tag | None:
    """定位表头同时包含姓名、简介、分工的唯一领导表格。"""
    for table in soup.select("table"):
        first_row = table.select_one("tr")
        headers = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in first_row.select("th, td")
        ] if first_row else []
        if headers[:3] == ["姓名", "简介", "分工"]:
            return table
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按领导表格行顺序提取姓名及简介列完整“现任……”句。"""
    soup = BeautifulSoup(html, "lxml")
    table = find_leader_table(soup)
    if not table:
        raise RuntimeError("未找到姓名、简介、分工三列领导表格")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for tr in table.select("tr")[1:]:
        cells = tr.select("td")
        if len(cells) < 3:
            continue
        name = re.sub(r"\s+", "", clean_text(cells[0].get_text(" ", strip=True)))
        profile = clean_text(cells[1].get_text(" ", strip=True))
        match = re.search(r"现任[^。]*。", profile)
        evidence = (
            clean_text(match.group(0)).removeprefix("现任").rstrip("。").strip()
            if match
            else ""
        )
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not evidence:
            continue
        if name in seen_names:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_guangzhou_port_profile_current_sentence_v2",
                "selector_summary": "table[姓名,简介,分工]；name=第1列；evidence=第2列完整现任句；detail=none",
            }
        )

    if not rows:
        raise RuntimeError("领导表格未提取到有效人物")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
