from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0611",
    "page_type": "人物表格页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "leader_region_selector": "#zoom.j-fontContent.newscontnet",
    "person_paragraph_selector": "p",
    "risk_flag": "正文同时包含历史履历与工作分工，只读取当前人物简介段中的现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩正文排版空白，不改变原文语义。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """清除姓名中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """在最小正文范围内按段落顺序提取姓名及完整“现任……”句。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导工作分工正文 #zoom")

    rows: list[dict] = []
    for paragraph in region.select(page_rule["person_paragraph_selector"]):
        paragraph_text = clean_text(paragraph.get_text(" ", strip=True))
        if "现任" not in paragraph_text or "，" not in paragraph_text:
            continue
        name = clean_name(paragraph_text.split("，", 1)[0])
        evidence_match = re.search(r"现任[^。]*。", paragraph_text)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not evidence_match:
            continue
        evidence = clean_text(evidence_match.group(0))
        evidence = re.sub(r"^现任\s*", "", evidence)
        evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence)
        evidence = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", evidence)
        evidence = re.sub(r"\s*([、，,；;：:])\s*", r"\1", evidence).removesuffix("。").strip()
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_hefei_police_current_sentence_v1",
                "selector_summary": (
                    "region=#zoom.j-fontContent.newscontnet；"
                    "person=正文p含现任；name=首个逗号前；evidence=现任[^。]*。"
                ),
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
