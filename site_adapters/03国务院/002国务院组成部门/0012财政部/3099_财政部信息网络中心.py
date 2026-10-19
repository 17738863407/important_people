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
    "rule_id": "3099",
    "page_type": "人物列表完整页",
    "structure_group": "领导简介正文姓名职务行",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofInfoNetworkCenterLeaderIntroParser_v2",
    "leader_region_selector": "div.TRS_Editor p",
    "risk_flag": "姓名和复合职务以全角空格排版；共同简介页面无独立人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一正文排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按TRS_Editor段落顺序解析全角空格分隔的姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for paragraph in soup.select(rule["leader_region_selector"]):
        raw_text = paragraph.get_text(" ", strip=True)
        match = re.fullmatch(
            r"\s*(?P<name>[\u4e00-\u9fff](?:[\s\u3000]*[\u4e00-\u9fff]){1,3}?)[\s\u3000]{2,}(?P<duty>.+?)\s*",
            raw_text,
        )
        if not match:
            continue
        duty = _clean_text(match.group("duty")).replace("主 任", "主任")
        records.append(
            {
                "name": "".join(match.group("name").split()),
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": "div.TRS_Editor p中的姓名与职务原文行",
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
