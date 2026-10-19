from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3127",
    "domain": "ybj.jiangxi.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "leader_list_h2_first_h3_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_html",
    "parser": "page_inline_leader_list_h2_first_h3_role_v1",
    "leader_region_selector": ".list_ldxx",
    "person_block_selector": ":scope > li",
    "name_selector": "h2",
    "duty_selector": "h3:first-of-type",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "每个人物项还含分工和简历h3；仅第一条h3是原始职务字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩姓名和职务节点中的排版空白，不改写职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表人物项顺序提取h2姓名和第一条h3原始职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in region.find_all("li", recursive=False):
        name_node = block.find("h2")
        duty_node = block.find("h3")
        if name_node is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        if duty.startswith(("分工", "简历")):
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.list_ldxx；person=:scope > li；"
                    "name=h2；duty=first h3；exclude=分工/简历"
                ),
            }
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
