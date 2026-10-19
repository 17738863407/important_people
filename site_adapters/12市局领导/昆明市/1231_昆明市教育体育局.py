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
    "rule_id": "1231",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_edu_duty_colon_name_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_edu_duty_colon_name_links_v1",
    "leader_region_selector": ".right.leadership .leadership-item-data",
    "name_selector": ".leadership-item-data a[href]",
    "duty_selector": ".leadership-item-data a[href]",
    "detail_link_selector": ".leadership-item-data a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_list_links",
        "max_detail_links": 20,
    },
    "risk_flag": "页面存在空职务分组，只接受含完整职务冒号姓名文本的人物链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def split_duty_name(text: str) -> tuple[str, str]:
    value = normalize_space(text)
    match = re.fullmatch(r"(?P<duty>[^：:]{2,80})[：:](?P<name>[\u4e00-\u9fa5\s]{2,8})", value)
    if not match:
        return "", ""
    name = re.sub(r"\s+", "", match.group("name"))
    return name, normalize_space(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物链接DOM顺序解析职务、姓名和真实详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".right.leadership .leadership-item-data a[href]"):
        evidence = normalize_space(link.get_text(" ", strip=True))
        name, duty = split_duty_name(evidence)
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", name) or not duty or name in seen:
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


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
