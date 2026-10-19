from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2558",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_ecology_duty_name_directory_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_kunming_ecology_duty_name_directory_v1",
    "leader_region_selector": ".right",
    "name_selector": "领导标题末尾姓名",
    "duty_selector": "领导标题中姓名前原始职务",
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_person_links",
        "detail_link_selector": ".right a[href]",
        "max_detail_links": 30,
    },
    "risk_flag": "second_page_contains_historical_organization_duties",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".right",
            "links": "a[href]",
            "title_pattern": "职务+空格+姓名",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML第一页标题链接直接包含领导职务、姓名和详情链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析第一页“职务 姓名”标题链接，排除日期和机构职责旧文。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".right")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("a[href]"):
        title = normalize_space(link.get_text(" ", strip=True))
        href = str(link.get("href", "")).strip()
        if "/c/" not in href or not title:
            continue
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,4})", title)
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty").strip()
        if not re.search(r"党组|局长|调研员|工程师|专员|组长|站长", duty):
            continue
        if any(word in duty for word in ("工作职责", "主要职责", "关于调整", "内设机构")):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, href),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".right第一页；职务姓名标题链接；动态href",
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
