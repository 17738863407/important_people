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
    "rule_id": "2702",
    "page_type": "多人物详情合并页",
    "structure_group": "Vue现任领导卡片",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "TiwteRenderedLeaderCardsParser_v2",
    "leader_region_selector": "main.main .leader li",
    "name_selector": "h3",
    "duty_selector": "em",
    "detail_link_selector": "a[href*='/Detail/Detail?id=']",
    "detail_strategy": {"required": False, "mode": "list_card_link"},
    "risk_flag": "入口为Vue空壳，必须使用浏览器渲染；人物与详情链接必须从当前卡片动态抽取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按Vue渲染后的现任领导卡片DOM顺序抽取数据。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select("main.main .leader li"):
        name_node = card.select_one("h3")
        duty_node = card.select_one("em")
        link_node = card.select_one("a[href*='/Detail/Detail?id=']")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        detail_url = urljoin(base_url, link_node.get("href", "")) if link_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": PAGE_RULE["parser"],
                "selector_summary": "main.main .leader li；h3姓名；em职务；卡片Detail/Detail链接；按渲染DOM顺序",
            }
        )
    if not records:
        raise RuntimeError("Vue现任领导卡片未解析到人物记录")
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
