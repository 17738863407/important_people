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
    "rule_id": "0746",
    "page_type": "人物分组名单页",
    "structure_group": "职务标题与后续姓名锚点",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "LanzhouCppccGroupedNamesParser_v2",
    "leader_region_selector": "div.title",
    "name_selector": "div.text a",
    "risk_flag": "姓名锚点当前href为空，不得用入口页填充详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一网页排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def _iter_name_links(title_node: Tag, selector: str) -> list[Tag]:
    """读取当前职务标题之后、下一职务标题之前的姓名锚点。"""
    links: list[Tag] = []
    for sibling in title_node.next_siblings:
        if isinstance(sibling, Tag) and "title" in (sibling.get("class") or []):
            break
        if isinstance(sibling, Tag):
            links.extend(sibling.select(selector))
    return links


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按网页分组顺序解析职务标题及其姓名列表。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for title in soup.select(rule["leader_region_selector"]):
        evidence = _clean_text(title.get_text(" ", strip=True))
        if not evidence:
            continue
        for link in _iter_name_links(title, rule["name_selector"]):
            name = _clean_name(link.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or (name, evidence) in seen:
                continue
            seen.add((name, evidence))
            href = (link.get("href") or "").strip()
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": "div.title职务分组；后续div.text a姓名",
                }
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
