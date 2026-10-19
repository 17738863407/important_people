from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0357",
    "page_type": "人物列表完整页",
    "structure_group": "hefei_construction_article_bold_leaders_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "parser": "hefei_construction_article_bold_leaders_v1",
    "leader_region_selector": "div.wenzhang div.wzcon.j-fontContent",
    "name_selector": ":scope > p > b",
    "duty_selector": ":scope > p > b",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP返回521，正文中职务段后紧邻分工段，须仅解析加粗姓名职务行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _compact_text(value: str) -> str:
    """仅移除网页排版空白，不改写姓名或职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按正文加粗段落的原始顺序解析“姓名（职务）”人物行。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域命中数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for node in regions[0].select(page_rule["name_selector"]):
        text = _compact_text(node.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u3400-\u9fff·]{2,10})[（(]([^）)]+)[）)]", text)
        if not match:
            continue
        name, evidence = match.groups()
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )

    if not records:
        raise RuntimeError("领导正文中未找到可核验的姓名职务行")
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
