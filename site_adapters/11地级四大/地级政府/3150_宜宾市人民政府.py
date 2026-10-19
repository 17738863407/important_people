from __future__ import annotations

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
    "rule_id": "3150",
    "page_type": "人物卡片页",
    "structure_group": "领导卡片姓名职务字段",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "YibinGovernmentLeaderCardParser_v2",
    "leader_region_selector": ".leaders .leaders-item1, .leaders .leaders-item",
    "name_selector": ".info p.name",
    "duty_selector": ".info p.zw",
    "detail_link_selector": "a[href]",
    "risk_flag": "首张主卡片与其余卡片类名不同，须合并选择并按DOM顺序解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """仅归一排版空白，保留职务原始语义及标点。"""
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    return " ".join(text.split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按当前页面DOM顺序解析领导卡片强结构字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for card in soup.select(rule["leader_region_selector"]):
        name_node = card.select_one(rule["name_selector"])
        duty_node = card.select_one(rule["duty_selector"])
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        evidence = _clean_text(duty_node.get_text(" ", strip=True))
        if not name or not evidence or (name, evidence) in seen:
            continue
        seen.add((name, evidence))
        link = card.select_one(rule["detail_link_selector"])
        href = (link.get("href") or "").strip() if link else ""
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": rule["parser"],
                "selector_summary": ".leaders卡片 > .info p.name + p.zw；详情=a[href]",
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
