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
    "rule_id": "0332",
    "page_type": "多人物详情合并页",
    "structure_group": "csc_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".list-c li",
    "name_selector": ".list-c h3",
    "duty_selector": ".list-c p",
    "detail_link_selector": ".list-c a[href]",
    "detail_strategy": {"required": False, "mode": "list_card_link"},
    "risk_flag": "普通HTTP可能受动态防护，需公共在线浏览器链路取得人物卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导卡片DOM顺序提取姓名、原始职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in soup.select(page_rule["leader_region_selector"]):
        name_node = item.select_one("h3")
        duty_node = item.select_one("p")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True)))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        link = item.select_one("a[href]")
        detail_url = urljoin(final_url, link.get("href", "")) if link else ""
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": page_rule["parser"],
                "selector_summary": ".list-c li；h3姓名；p职务；卡片href详情；按DOM顺序",
            }
        )
    if not records:
        raise RuntimeError("国家留学基金管理委员会现任领导卡片未解析到人物记录")
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
