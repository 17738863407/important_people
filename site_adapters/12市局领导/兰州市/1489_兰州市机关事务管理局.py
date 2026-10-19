from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1489",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_affairs_profile_paragraph_name_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_affairs_profile_paragraph_name_duty_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom p首个逗号前姓名",
    "duty_selector": "#zoom p姓名后至性别字段前原始机构职务短语",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "profile_paragraphs_mix_name_duty_gender_and_biography_fields",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#zoom",
            "paragraph_selector": "p",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线HTML正文5个简介段落直接包含姓名、完整机构职务和随后性别字段",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按简介段落顺序提取姓名及性别字段前完整原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    pattern = re.compile(
        r"^(?P<name>[\u4e00-\u9fff·]{2,8})，(?P<duty>.+?)，(?=[男女]，)"
    )
    for paragraph in container.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if match is None:
            continue
        name = match.group("name")
        duty = normalize_space(match.group("duty"))
        if name in seen_names or not re.search(r"书记|局长|副局长|调研员|党组成员", duty):
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#zoom简介段落；首个逗号前姓名；姓名后至明确性别字段前完整原始机构职务短语",
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
