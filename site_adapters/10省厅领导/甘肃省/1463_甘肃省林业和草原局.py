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
    "rule_id": "1463",
    "domain": "lycy.gansu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "gansu_forestry_leader_detail_directory_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_forestry_leader_detail_directory_v1",
    "leader_region_selector": ".zfxxgk_zdgkc .xxgkleader",
    "name_selector": "h4",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "online_first_detail_directory",
        "detail_collector_type": "browser",
        "detail_directory_selector": ".leader-list.sbox .bd > a[href]",
        "detail_name_selector": "p.name",
        "detail_duty_selector": "p.position",
    },
    "risk_flag": "主列表卡片仅含姓名；首个动态人物页的其他领导区域同时列出全部人物姓名、职务和链接",
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
    """从首个动态人物页的完整领导目录抽取全部人物。"""
    soup = BeautifulSoup(html, "html.parser")
    first_card = soup.select_one(str(page_rule["leader_region_selector"]))
    first_link = first_card.select_one(str(page_rule["detail_link_selector"])) if first_card else None
    if first_link is None:
        return []

    from crawler_core.fetcher import fetch_html_with_strategy

    first_detail_url = urljoin(final_url, str(first_link.get("href") or ""))
    strategy = page_rule["detail_strategy"]
    detail_result = fetch_html_with_strategy(
        first_detail_url,
        strategy="browser",
        force_browser=True,
        timeout=60,
    )
    detail_soup = BeautifulSoup(detail_result.html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in detail_soup.select(str(strategy["detail_directory_selector"])):
        name_node = link.select_one(str(strategy["detail_name_selector"]))
        duty_node = link.select_one(str(strategy["detail_duty_selector"]))
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(detail_result.final_url or first_detail_url, str(link.get("href") or "")),
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
