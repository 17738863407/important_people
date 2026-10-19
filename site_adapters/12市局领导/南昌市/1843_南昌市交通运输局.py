from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1843",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_transport_name_duty_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright",
    "parser": "page_nanchang_transport_name_duty_paragraphs_v2",
    "leader_region_selector": ".article-content",
    "name_selector": ".article-content p中姓名字段",
    "duty_selector": ".article-content p中职务字段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "requests_returns_403_and_assignment_and_profile_paragraphs_follow_each_duty_row",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".article-content", "row_selector": ".article-content p"},
        "api": {"enabled": False, "reason": "当前HTTPS渲染正文以独立段落直出姓名字段和职务字段"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_evidence_duty(text: str) -> str:
    """清理当前页职务字段中的独立状态标记与确定性排版空格。"""
    evidence = re.sub(r"(?:（兼）|\(兼\)|[<＜]兼[>＞])", "", normalize_space(text))
    evidence = re.sub(r"\s+([，。；：、])", r"\1", evidence)
    evidence = re.sub(r"([，；：、])\s+", r"\1", evidence)
    evidence = re.sub(r"(?<=[\u4e00-\u9fff）)])\s+(?=[\u4e00-\u9fff（(])", "", evidence)
    return re.sub(r"。$", "", evidence).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文DOM顺序仅解析独立姓名、职务字段行。"""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".article-content")
    if content is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in content.select("p"):
        evidence = normalize_space(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"姓名[:：]\s*(?P<name>[\u4e00-\u9fff·\s]{2,12}?)\s+职务[:：]\s*(?P<duty>.+)", evidence)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        duty = clean_evidence_duty(match.group("duty"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "HTTPS渲染后.article-content p按DOM顺序；仅姓名和职务字段行；排除后续分工、分管、联系及查看详情简介段",
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
