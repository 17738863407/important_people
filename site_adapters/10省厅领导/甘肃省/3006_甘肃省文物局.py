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
    "rule_id": "3006",
    "domain": "wwj.gansu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "gansu_cultural_relics_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_cultural_relics_leader_cards_v1",
    "leader_region_selector": "#m1",
    "card_selector": "li",
    "name_duty_selector": "direct p",
    "detail_link_selector": "direct a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_card_links",
    },
    "risk_flag": "普通HTTP返回412防护页；#m1还含栏目导航和专题图片，人物卡片须同时具有直接a图片链接和两个直接p字段",
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
    """按渲染后局领导卡片DOM顺序抽取姓名、职务和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in region.select(str(page_rule["card_selector"])):
        fields = card.find_all("p", recursive=False)
        link = card.find("a", href=True, recursive=False)
        if len(fields) != 2 or link is None or link.select_one("img") is None:
            continue
        name = clean_name(fields[0].get_text(" ", strip=True))
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
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
