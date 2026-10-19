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
    "rule_id": "2681",
    "page_type": "动态人物链接页",
    "structure_group": "姓名职务组合链接",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "ShenzhenCppccLeaderAnchorParser_v2",
    "leader_region_selector": ".articleCont .news-ld1",
    "detail_link_selector": "a[href]",
    "risk_flag": "requests存在SSL BAD_ECPOINT，online需降级Playwright渲染",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    """组合字段仅去除排版空白。"""
    return "".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按渲染DOM顺序拆分“姓名（职务）”人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for region in soup.select(rule["leader_region_selector"]):
        for link in region.select(rule["detail_link_selector"]):
            evidence = _compact_text(link.get_text(" ", strip=True))
            match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})（(?P<duty>[^）]+)）", evidence)
            if match is None or match.group("name") in seen:
                continue
            name = match.group("name")
            duty = match.group("duty")
            href = (link.get("href") or "").strip()
            seen.add(name)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": urljoin(base_url, href) if href else "",
                    "parser": rule["parser"],
                    "selector_summary": ".articleCont .news-ld1内姓名（职务）链接",
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
