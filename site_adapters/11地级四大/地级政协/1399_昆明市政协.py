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
    "rule_id": "1399",
    "page_type": "人物分组卡片页",
    "structure_group": "职务标题与相邻人物卡片盒",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "KunmingCppccGroupedLeaderCardParser_v2",
    "leader_region_selector": ".list-ld .list-ld-title",
    "name_selector": ".list-ld-item a[href] p",
    "detail_link_selector": ".list-ld-item a[href]",
    "risk_flag": "各职务标题只适用于其相邻list-ld-box内人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一页面排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按职务标题及相邻人物盒的DOM顺序解析领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for title in soup.select(rule["leader_region_selector"]):
        evidence = _clean_text(title.get_text(" ", strip=True))
        box = title.find_next_sibling("div", class_="list-ld-box")
        if not evidence or box is None:
            continue
        for link in box.select(rule["detail_link_selector"]):
            name_node = link.select_one("p")
            name = _clean_name(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
            href = (link.get("href") or "").strip()
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or (name, evidence) in seen:
                continue
            seen.add((name, evidence))
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": ".list-ld-title职务 + 相邻.list-ld-box人物链接",
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
