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
    "rule_id": "2661",
    "page_type": "人物列表完整页",
    "structure_group": "监管局领导简介组合链接列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofShenzhenSupervisionLeaderListParser_v2",
    "leader_region_selector": "div.listBox ul.liBox li a[title][href]",
    "detail_link_selector": "a[title][href]",
    "risk_flag": "页面含导航与脚本分页链接，必须限定领导简介列表中的组合字段链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一页面排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导简介列表DOM顺序拆分“职务：姓名”组合字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for link in soup.select(rule["leader_region_selector"]):
        evidence = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<duty>.+?)[：:]\s*(?P<name>[\u4e00-\u9fff·]{2,8})", evidence)
        if not match or match.group("name") in seen:
            continue
        name = match.group("name")
        seen.add(name)
        href = _clean_text(link.get("href", ""))
        records.append(
            {
                "name": name,
                "duty": _clean_text(match.group("duty")),
                "evidence": _clean_text(match.group("duty")),
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": rule["parser"],
                "selector_summary": "div.listBox ul.liBox内领导a[title][href]组合字段",
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
