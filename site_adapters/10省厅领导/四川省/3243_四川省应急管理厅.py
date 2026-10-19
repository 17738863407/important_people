from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3243",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_emergency_leader_card_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "online",
    "parser": "V004_card_person_v1",
    "leader_region_selector": "ul.leader-list > li.leader-list-info",
    "name_selector": ".leaders-name-wrap",
    "duty_selector": ".leaders-position",
    "detail_link_selector": ".buttons a[href]",
    "detail_name_selector": ".right-container .leader-name",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析四川省应急管理厅厅领导卡片。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    item_selector = str(page_rule["leader_region_selector"])
    name_selector = str(page_rule["name_selector"])
    duty_selector = str(page_rule["duty_selector"])
    detail_link_selector = str(page_rule["detail_link_selector"])
    detail_name_selector = str(page_rule["detail_name_selector"])
    items = soup.select(item_selector)
    if not items:
        raise RuntimeError(f"领导卡片未命中：{item_selector}")

    rows: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for source_order, item in enumerate(items, start=1):
        name_node = item.select_one(name_selector)
        duty_node = item.select_one(duty_selector)
        if not name_node or not duty_node:
            errors.append(f"第{source_order}张卡片缺少姓名或职务节点")
            continue

        name = re.sub(r"\s+", "", name_node.get_text("", strip=True))
        evidence = re.sub(r"\s+", "", duty_node.get_text("", strip=True))
        evidence = re.sub(r"[（(]兼[）)]", "", evidence).strip("，、； ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not evidence:
            errors.append(f"第{source_order}张卡片姓名或职务无效")
            continue
        if name in seen:
            errors.append(f"第{source_order}张卡片姓名重复：{name}")
            continue

        seen.add(name)
        link = item.select_one(detail_link_selector)
        href = str(link.get("href", "") if link else "").strip()
        detail_url = ""
        if href and not href.lower().startswith(("#", "javascript:", "mailto:")):
            candidate_url = urljoin(final_url or str(page_rule.get("url", "")), href)
            candidate_path = urlparse(candidate_url).path
            if re.search(r"/leaderInfo\.shtml$", candidate_path):
                try:
                    detail_result = fetch_html_with_strategy(
                        candidate_url,
                        strategy=str(page_rule.get("fetch_mode", "online")),
                    )
                    detail_soup = BeautifulSoup(detail_result.html, "html.parser")
                    detail_name_node = detail_soup.select_one(detail_name_selector)
                    detail_name = re.sub(
                        r"\s+",
                        "",
                        detail_name_node.get_text("", strip=True) if detail_name_node else "",
                    )
                    if detail_name == name:
                        detail_url = detail_result.final_url
                except Exception:
                    detail_url = ""

        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": (
                    f"{item_selector} 内 {name_selector} + {duty_selector}；"
                    f"{detail_link_selector} 经 {detail_name_selector} 验证"
                ),
            }
        )

    if errors:
        raise RuntimeError("领导卡片解析失败：" + "；".join(errors))
    if not rows:
        raise RuntimeError("领导卡片未解析出有效人物")
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
