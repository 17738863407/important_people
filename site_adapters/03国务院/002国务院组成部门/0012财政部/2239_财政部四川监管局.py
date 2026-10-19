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
    "rule_id": "2239",
    "page_type": "人物列表完整页",
    "structure_group": "监管局概况领导链接列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofSichuanSupervisionLeaderListParser_v2",
    "leader_region_selector": "ul.liBox li",
    "detail_link_selector": "a[title][href]",
    "risk_flag": "同一列表含办公室与业务处室条目，必须以明确领导职务文本限定人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一HTML属性中的排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按概况列表DOM顺序提取具有局领导职务标签的链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for item in soup.select(rule["leader_region_selector"]):
        link = item.select_one(rule["detail_link_selector"])
        evidence = _clean_text(link.get("title", "") if link else "")
        if not link or ("局长" not in evidence and "党组" not in evidence):
            continue
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,8})", evidence)
        if not match or match.group("name") in seen:
            continue
        name = match.group("name")
        seen.add(name)
        href = _clean_text(link.get("href", ""))
        duty = _clean_text(match.group("duty"))
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": rule["parser"],
                "selector_summary": "ul.liBox li内含明确局领导职务的a[title][href]",
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
