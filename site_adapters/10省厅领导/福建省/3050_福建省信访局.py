from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3050",
    "page_type": "机构概况领导卡片",
    "structure_group": "fujian_petition_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "page_inline",
    "parser": "page_inline_fujian_petition_leader_cards_v2",
    "leader_region_selector": ".ldxx_box",
    "card_selector": ".ldxx_list .ldxx_nr",
    "name_selector": "h4",
    "duty_selector": "p",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_card_link",
    },
    "risk_flag": "从主表注入机构概况入口；仅按领导信息卡片原序读取姓名及职务，详情链接取自同一卡片；不回退旧人物页或混入机构设置",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """直接读取当前机构概况页的领导卡片，不依赖旧详情入口。"""
    soup = BeautifulSoup(html, "html.parser")
    for node in reversed(list(soup.find_all(True))):
        if (
            node.has_attr("hidden")
            or str(node.get("aria-hidden", "")).lower() == "true"
            or set(node.get("class", [])).intersection({"hidden", "hide", "d-none"})
            or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", str(node.get("style", "")), re.I)
        ):
            node.decompose()
    regions = soup.select(str(page_rule["leader_region_selector"]))
    if len(regions) != 1:
        raise RuntimeError("领导信息区域缺失或不唯一")
    cards = regions[0].select(str(page_rule["card_selector"]))
    if not cards:
        raise RuntimeError("领导卡片为空")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in cards:
        name_node = card.select_one(str(page_rule["name_selector"]))
        duty_node = card.select_one(str(page_rule["duty_selector"]))
        if name_node is None or duty_node is None:
            raise RuntimeError("领导卡片姓名或职务字段缺失")
        name = clean_name(name_node.get_text(" ", strip=True))
        evidence = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            raise RuntimeError(f"领导卡片姓名异常或重复：{name}")
        if not evidence:
            raise RuntimeError(f"领导卡片职务为空：{name}")
        link = card.select_one(str(page_rule["detail_link_selector"]))
        href = str(link.get("href") or "").strip() if link else ""
        candidate = urljoin(final_url, href) if href and not href.startswith("#") else ""
        parts = urlsplit(candidate)
        if parts.scheme not in {"http", "https"} or candidate.rstrip("/") == final_url.rstrip("/"):
            candidate = ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": candidate,
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
