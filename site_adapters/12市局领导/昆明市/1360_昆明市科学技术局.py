from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1360",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_science_leadership_group_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_science_leadership_group_v1",
    "leader_region_selector": ".right.leadership",
    "name_selector": ".leadership-item-data a[href] p",
    "duty_selector": ".zwbox h3",
    "detail_link_selector": ".leadership-item-data a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_group_links",
        "max_detail_links": 20,
    },
    "risk_flag": "首个领导分组内部另含当前为空的局长子组，必须按直接子组边界解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def direct_child_divs(node: object, class_name: str) -> list[object]:
    return [
        child
        for child in node.find_all("div", class_=class_name, recursive=False)
        if getattr(child, "name", "") == "div"
    ]


def parse_container(container: object, base_url: str, page_rule: dict, seen: set[str]) -> list[dict[str, str]]:
    heading = container.select_one(".zwbox h3")
    duty = normalize_space(heading.get_text(" ", strip=True) if heading else "")
    if not duty:
        return []
    rows: list[dict[str, str]] = []
    for link in container.select(".data-list .leadership-item-data a[href]"):
        name_node = link.select_one("p")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": urljoin(base_url, link.get("href", "")),
                "evidence": duty,
                "confidence": "high",
                "parser": page_rule["parser"],
            }
        )
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导分组及其直接子组顺序解析人物。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".right.leadership")
    if region is None:
        return []
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in region.select(".leadership-item"):
        subgroups = direct_child_divs(item, "two-list")
        if subgroups:
            for subgroup in subgroups:
                rows.extend(parse_container(subgroup, base_url, page_rule, seen))
        else:
            rows.extend(parse_container(item, base_url, page_rule, seen))
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
