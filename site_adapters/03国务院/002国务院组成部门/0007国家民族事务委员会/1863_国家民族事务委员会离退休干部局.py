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
    "rule_id": "1863",
    "page_type": "人物列表完整页",
    "structure_group": "部门领导标题至联系方式标题之间职务姓名段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NeacRetiredCadresLeaderParagraphParser_v2",
    "leader_region_selector": ".f1-3-1 .p3",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "须以部门领导和联系方式标题限定边界；姓名后可能带援派说明",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """在部门领导标题边界内按段落顺序抽取职务与姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".f1-3-1 .p3")
    if region is None:
        raise RuntimeError("未找到机构正文 .f1-3-1 .p3")

    rows: list[dict] = []
    in_leader_section = False
    for paragraph in region.select("p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        if evidence.rstrip("：:") == "部门领导":
            in_leader_section = True
            continue
        if evidence.rstrip("：:") == "联系方式":
            break
        if not in_leader_section:
            continue
        match = re.fullmatch(
            r"(?P<duty>[^：:]+)\s*[：:]\s*(?P<name>[\u4e00-\u9fff·]{2,4})(?:（[^）]+）)?",
            evidence,
        )
        if not match:
            continue
        duty = _clean_text(match.group("duty"))
        rows.append(
            {
                "name": match.group("name"),
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".f1-3-1 .p3 p；部门领导至联系方式边界",
            }
        )

    if not rows:
        raise RuntimeError("部门领导边界内未解析到职务姓名记录")
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
