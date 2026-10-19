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
    "rule_id": "1443",
    "domain": "lsj.fujian.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "fujian_grain_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_fujian_grain_leader_cards_v1",
    "leader_region_selector": "div.con_ldxx",
    "name_selector": ".leader_content h3, .people_list li h6",
    "duty_selector": ".leader_content p, .people_list li p",
    "detail_link_selector": ".leader_content a[href], .people_list li a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_card_links",
    },
    "risk_flag": "首人使用独立主卡片，其余人物使用列表卡片；须保持主卡片在前的页面顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def build_row(container: object, base_url: str, name_selector: str, duty_selector: str) -> dict[str, str] | None:
    name_node = container.select_one(name_selector)
    duty_node = container.select_one(duty_selector)
    link = container.select_one("a[href]")
    name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
    evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence:
        return None
    return {
        "name": name,
        "duty": evidence,
        "evidence": evidence,
        "detail_url": urljoin(base_url, str(link.get("href") or "")) if link else "",
    }


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按主领导卡片、其余领导卡片的网页顺序抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(str(page_rule["leader_region_selector"]))
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    containers = list(root.select(".leader_content")) + list(root.select(".people_list li"))
    for container in containers:
        row = build_row(container, final_url, "h3, h6", "p")
        if row is None or row["name"] in seen:
            continue
        seen.add(row["name"])
        rows.append(row)
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
