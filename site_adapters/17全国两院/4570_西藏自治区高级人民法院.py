from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4570",
    "page_type": "省级法院同页领导班子",
    "structure_group": "tibet_high_court_leadership_article_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_tibet_high_court_leadership_article_v1",
    "leader_region_selector": "div.text",
    "name_selector": "div.text中独立姓名p",
    "duty_selector": "姓名后首个以西藏自治区高级人民法院开头的p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "同一领导班子文章按姓名、职务、简历分组；凡位于该领导分组且职务以本院名称开头者均保留，包括委员、专职委员和巡视员。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("div.text")
    if region is None:
        raise RuntimeError("领导班子文章缺少div.text正文")
    paragraphs = [re.sub(r"[\s\u3000\xa0]+", "", p.get_text(" ", strip=True)) for p in region.select("p")]
    paragraphs = [text for text in paragraphs if text]
    subject = "西藏自治区高级人民法院"
    rows: list[dict[str, str]] = []
    for index, name in enumerate(paragraphs[:-1]):
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        raw_duty = paragraphs[index + 1]
        if not raw_duty.startswith(subject):
            continue
        duty = raw_duty
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "confidence": "high", "parser": str(page_rule.get("parser", "")),
            "selector_summary": "div.text领导班子非空段落；独立姓名后本院完整职务；委员及巡视员同样保留",
        })
    if not rows:
        raise RuntimeError("领导班子文章未提取到人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
