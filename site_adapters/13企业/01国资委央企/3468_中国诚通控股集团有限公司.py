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
    "rule_id": "3468",
    "page_type": "职务分组名单页",
    "structure_group": "中国诚通党委会人物卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CctPartyCommitteeCardParser_v1",
    "leader_region_selector": ".leadBox .leadOnePer:not(.lastPer)",
    "name_selector": ".leadOneTit a[istitle]",
    "duty_selector": ".leadOneTit:nth-of-type(2) a",
    "detail_link_selector": ".leadOneTit a[istitle][href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "当前入口仅为党委会分组；排除display:none的lastPer占位卡片，不合并董事会或经营班子",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按党委会卡片DOM顺序解析姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select(".leadBox .leadOnePer:not(.lastPer)"):
        name_link = card.select_one(".leadOneTit a[istitle]")
        title_nodes = card.select(".leadOneTit a")
        if name_link is None or len(title_nodes) < 2:
            continue
        name = re.sub(r"\s+", "", name_link.get_text(" ", strip=True))
        evidence = _clean_text(title_nodes[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(base_url, str(name_link.get("href", "")))
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".leadBox .leadOnePer非占位卡；首个leadOneTit为姓名、第二个为职务",
            }
        )
    if not records:
        raise RuntimeError("中国诚通党委会卡片未解析到人物记录")
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
