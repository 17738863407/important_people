from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2559",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_ecology_homepage_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "raw_http",
    "parser": "page_lanzhou_ecology_homepage_leader_paragraphs_v1",
    "leader_region_selector": "#public_content_list .leader",
    "name_selector": ".leader p:not(.top)中党组字段前姓名",
    "duty_selector": ".leader p:not(.top)从党组字段开始的原始职务",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_link_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "online_script_redirect_leaves_homepage_while_raw_http_contains_authoritative_leader_table",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#public_content_list .leader",
            "row_selector": "p:not(.top)",
        },
        "api": {
            "enabled": False,
            "reason": "当前原始HTTP首页直接包含领导班子6条姓名职务，raw_http防止页面脚本跳转离开首页",
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
    return re.sub(r"\s*([、，。；：])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按首页领导班子段落顺序，以党组字段为边界拆分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#public_content_list .leader")
    if container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for paragraph in container.select("p:not(.top)"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        marker_index = text.find("党组")
        if marker_index <= 0:
            continue
        name = re.sub(r"\s+", "", text[:marker_index])
        duty = normalize_space(text[marker_index:])
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not duty
            or name in seen_names
        ):
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "原始HTTP首页#public_content_list .leader；排除表头p.top；以党组字段为边界拆分姓名和原始职务",
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
