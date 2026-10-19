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
    "rule_id": "3445",
    "page_type": "人物列表完整页",
    "structure_group": "人物卡片标题中的姓名与职务",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "YinchuanCppccLeaderCardParser_v2",
    "leader_region_selector": "#ldList a[href]",
    "risk_flag": "姓名可能含排版空格，必须以职务起始词前的边界切分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一卡片标题中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按人物卡片DOM顺序解析姓名、原始职务和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for link in soup.select(rule["leader_region_selector"]):
        card_text = _clean_text(link.get("title") or link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+(?=(?:党组|副主席))(.+)", card_text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = _clean_text(match.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "parser": rule["parser"],
                "selector_summary": "#ldList人物卡片标题；职务起始词前边界切分",
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
