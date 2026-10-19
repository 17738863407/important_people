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
    "rule_id": "2842",
    "page_type": "多人物详情合并页",
    "structure_group": "领导正文姓名冒号职务列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofBudgetReviewTextLeadersParser_v2",
    "leader_region_selector": "div.TRS_Editor p",
    "risk_flag": "共同领导简介正文无独立人物详情链接，姓名含全角排版空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一正文排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按TRS_Editor段落顺序拆分“姓名：职务”。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for paragraph in soup.select(rule["leader_region_selector"]):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})\s*[：:]\s*(?P<duty>.+)",
            evidence,
        )
        if not match:
            continue
        records.append(
            {
                "name": "".join(match.group("name").split()),
                "duty": _clean_text(match.group("duty")),
                "evidence": _clean_text(match.group("duty")),
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": "div.TRS_Editor p中的姓名冒号职务原文",
            }
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
