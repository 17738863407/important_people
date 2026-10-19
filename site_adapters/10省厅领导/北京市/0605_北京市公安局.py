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
    "rule_id": "0605",
    "page_type": "人物表格页",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "profile_blocks",
    "parser": "beijing_police_profile_table_v3",
    "leader_region_selector": "div.view.TRS_UEDITOR",
    "name_selector": "当前人物简介段落开头",
    "duty_selector": "当前人物简介段落内完整现任句",
    "detail_link_selector": "",
    "locator_strategy": "custom_parse_page",
    "filter_policy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "单人物表格简介页；入口页本身不得作为详情页链接",
}


def _clean_text(value: object) -> str:
    """仅清理HTML排版空白，不改写原文语义和标点。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在领导正文最小范围内提取姓名及完整“现任……”原句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(page_rule["leader_region_selector"])
    if scope is None:
        return []

    for node in scope.select("p, td"):
        profile_text = _clean_text(node.get_text(" ", strip=True))
        name_match = re.match(r"(?P<name>[\u3400-\u9fff·]{2,8})，", profile_text)
        evidence_match = re.search(r"现任[^。]*。", profile_text)
        if name_match and evidence_match:
            evidence = re.sub(r"^现任\s*", "", evidence_match.group(0))
            evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence).removesuffix("。").strip()
            return [
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name_match.group("name"),
                    duty=evidence,
                    detail_url="",
                    evidence=evidence,
                    confidence=page_rule["confidence"],
                    parser=page_rule["parser"],
                )
            ]
    return []


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
