from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "2668",
    "page_type": "人物列表页",
    "structure_group": "hebei_data_bureau_leader_window_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "hebei_data_bureau_leader_window_v2",
    "leader_region_selector": ".ewb-work-items",
    "name_selector": ".work-name p",
    "duty_selector": ".work-jianli-p strong",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "人物姓名和职务位于同一列表项中，页面无独立人物详情链接。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """清理HTML排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按网页列表项的DOM顺序动态提取姓名和职务。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    records: list[object] = []
    for item in region.select(":scope > li"):
        name_node = item.select_one(page_rule["name_selector"])
        duty_nodes = item.select(page_rule["duty_selector"])
        if name_node is None or not duty_nodes:
            continue

        name = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            name_node.get_text(" ", strip=True),
        )
        duties = [
            _clean_text(node.get_text(" ", strip=True)) for node in duty_nodes
        ]
        duty = "；".join(dict.fromkeys(value for value in duties if value))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue

        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
