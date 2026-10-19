from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4535",
    "page_type": "检察院领导富文本段落",
    "structure_group": "hainan_procuratorate_richtext_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "richtext_sections",
    "parser": "page_hainan_procuratorate_richtext_paragraphs_v1",
    "leader_region_selector": "#zt",
    "name_selector": "领导标题后含海南省人民检察院职务的p前缀",
    "duty_selector": "同一p及紧邻续行",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "富文本无统一卡片结构；连续解析“海南省人民检察院领导”和“检察委员会专职委员”两个领导分组的职务段落，并合并跨段续行。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按领导与专职委员两个连续分组解析职务段落。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("#zt")
    if region is None:
        raise RuntimeError("未找到领导简介正文 #zt")
    active = False
    paragraphs: list[str] = []
    for node in region.find_all(["h2", "p"], recursive=False):
        text = re.sub(r"[\s\u00a0\u3000]+", "", node.get_text(" ", strip=True))
        if node.name == "h2":
            if text == "海南省人民检察院领导" or "检察委员会专职委员" in text:
                active = True
                continue
            if active:
                break
        elif active and text:
            paragraphs.append(text)
    rows: list[dict[str, str]] = []
    for index, text in enumerate(paragraphs):
        marker = text.find("海南省人民检察院")
        if marker <= 0:
            continue
        name = text[:marker]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        evidence = text[marker:]
        if index + 1 < len(paragraphs):
            continuation = paragraphs[index + 1]
            if continuation.startswith("海南省人民检察院纪检监察组") or continuation.startswith("党组书记"):
                evidence += continuation
        if not any(title in evidence for title in ("检察长", "副检察长", "党组成员", "政治部主任", "纪检监察组组长", "检察委员会委员", "专职委员")):
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "#zt内领导与专职委员两个h2分组按含机构全称的职务p提取，跨段职务续行合并"})
    if not rows:
        raise RuntimeError("领导简介正文未提取到目标领导")
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
