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
    "rule_id": "0215",
    "page_type": "人物列表完整页",
    "structure_group": "领导班子卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ChinaAiiLeaderCardParser_v2",
    "leader_region_selector": "li.w-list-item",
    "name_selector": "h5.w-list-title",
    "duty_selector": "div.w-list-desc",
    "detail_link_selector": "a.w-list-link[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "online因页面脚本文字中的验证码标记误判为可疑；当前原始HTTP已核验含完整卡片，使用raw_http；另须排除变量占位模板",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导卡片DOM顺序抽取姓名、职务和真实独立详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for card in soup.select("li.w-list-item"):
        name_node = card.select_one("h5.w-list-title")
        duty_node = card.select_one("div.w-list-desc")
        link_node = card.select_one("a.w-list-link[href]")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        href = _clean_text(str(link_node.get("href", ""))) if link_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        if not href or "$" in href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, href),
                "parser": PAGE_RULE["parser"],
                "selector_summary": "li.w-list-item；h5.w-list-title；div.w-list-desc；a.w-list-link[href]",
            }
        )
    if not records:
        raise RuntimeError("领导班子卡片未解析到人物记录")
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
