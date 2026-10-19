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
    "rule_id": "2675",
    "page_type": "人物目录详情页",
    "structure_group": "领导简介正文逐行姓名职务",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofTaxPolicyLeaderTextParser_v2",
    "leader_region_selector": "div.TRS_Editor",
    "risk_flag": "文章正文后含附件、相关文章与分享控件，必须限定TRS_Editor领导简介正文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一正文排版空白。"""
    return " ".join(str(value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按TRS_Editor直属行顺序提取姓名和明确职务。"""
    soup = BeautifulSoup(html, "html.parser")
    editor = soup.select_one(rule["leader_region_selector"])
    if editor is None:
        return []
    records: list[dict] = []
    for line in editor.find_all("div", recursive=False):
        evidence = _clean_text(line.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff]\s*[\u4e00-\u9fff])\s+(?P<duty>税政司(?:副)?司长)",
            evidence,
        )
        if not match:
            continue
        records.append(
            {
                "name": "".join(match.group("name").split()),
                "duty": match.group("duty"),
                "evidence": match.group("duty"),
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": "div.TRS_Editor直属div中的姓名与职务行",
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
