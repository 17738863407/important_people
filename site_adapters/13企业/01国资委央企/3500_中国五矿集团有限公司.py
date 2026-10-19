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
    "rule_id": "3500",
    "page_type": "人物列表完整页",
    "structure_group": "中国五矿高管团队职务姓名链接列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MinmetalsDutyColonNameParser_v2",
    "leader_region_selector": ".right .bodList li a[href]",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "列表正文按职务：姓名排列；详情页直接HTTP触发403防护",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按列表DOM顺序解析“职务：姓名”并保留当前条目的独立链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for link_node in soup.select(".right .bodList li a[href]"):
        text = _clean_text(link_node.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<duty>[^：:]{2,80})[：:](?P<name>[\u4e00-\u9fff·]{2,5})",
            text,
        )
        if match is None:
            continue
        name = match.group("name")
        evidence = match.group("duty").strip("，,、；; ")
        if name in seen_names:
            continue
        seen_names.add(name)
        href = (link_node.get("href") or "").strip()
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".right .bodList li a[href]；职务：姓名；当前a为详情",
            }
        )
    if not records:
        raise RuntimeError("中国五矿高管团队列表未解析到人物记录")
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
