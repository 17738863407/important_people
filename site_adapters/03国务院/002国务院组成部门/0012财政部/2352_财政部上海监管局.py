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
    "rule_id": "2352",
    "page_type": "人物列表完整页",
    "structure_group": "监管局概况领导链接列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofShanghaiSupervisionLeaderListParser_v2",
    "leader_region_selector": "div.mainboxerji a[href]",
    "detail_link_selector": "a[href]",
    "risk_flag": "页面含内设机构等非人物链接，必须以明确局长、巡视员或纪检组长职务限定人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一页面排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split()).strip(" ：:，,。；;")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按概况页DOM顺序拆分领导链接中的“职务 姓名”。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for link in soup.select(rule["leader_region_selector"]):
        evidence = _clean_text(link.get_text(" ", strip=True))
        if not re.search(r"局长|巡视员|纪检组长", evidence):
            continue
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,8})", evidence)
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
                "selector_summary": "div.mainboxerji内含明确领导职务的a[href]",
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
