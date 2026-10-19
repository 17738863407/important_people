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
    "rule_id": "0549",
    "page_type": "人物列表完整页",
    "structure_group": "kunming_fgw_biography_current_duty_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "kunming_fgw_biography_current_duty_v3",
    "leader_region_selector": ".content .activity p",
    "name_selector": "简历标题后的当前人物简介首句",
    "duty_selector": "当前人物简介中的完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "max_detail_links": 0,
    },
    "risk_flag": "正文为领导标题、简历、分工循环；职务标题可能跨段，必须只在每个简历块内提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([，。；、：])", r"\1", text)
    return re.sub(r"([，。；、：])\s+", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页人物顺序从各自简介块提取姓名和完整现任职务句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    paragraphs = soup.select(".content .activity p")
    for index, node in enumerate(paragraphs):
        if clean_text(node.get_text(" ", strip=True)) != "简历":
            continue
        biography = ""
        for candidate in paragraphs[index + 1 :]:
            biography = clean_text(candidate.get_text(" ", strip=True))
            if biography:
                break
        match = re.match(
            r"^(?P<name>[\u4e00-\u9fa5·]{2,4})\s*[，,].*?现\s*任\s*(?P<duty>[^。]+)[。.]",
            biography,
        )
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = clean_text(match.group("duty"))
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "kunming_fgw_biography_current_duty_v3",
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
