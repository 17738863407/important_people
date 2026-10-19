from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2413",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_water_name_duty_directory_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_water_name_duty_directory_v1",
    "leader_region_selector": ".right",
    "name_selector": "人物链接冒号前姓名",
    "duty_selector": "人物链接冒号后原始职务",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_person_links",
        "detail_link_selector": ".right a[href]",
        "max_detail_links": 20,
    },
    "risk_flag": "directory_also_contains_non_person_work_division_article",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".right",
            "links": "a[href]",
            "field_pattern": "姓名：职务",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML目录链接文本直接包含姓名和职务，href为人物详情页",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\u2002", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录DOM顺序解析“姓名：职务”人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".right")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a[href]"):
        text = normalize_space(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff\s]{2,8})\s*[：:]\s*(?P<duty>.+)", text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = match.group("duty").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
            continue
        if not re.search(r"党组|局长|主任|组长", duty) or "工作分工" in duty:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".right目录；姓名：职务人物链接；动态href",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
