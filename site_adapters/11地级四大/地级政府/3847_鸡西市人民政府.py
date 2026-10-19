from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析市长卡片及同一可见领导列表中的职务、姓名和详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    leader_nodes = [
        *soup.select(".mayor > p"),
        *soup.select("#tabCon_0 .leadList > li > span"),
    ]
    for node in leader_nodes:
        anchor = node.select_one(":scope > a[href]")
        if anchor is None:
            continue
        name = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        evidence = clean_text("".join(str(item) for item in anchor.previous_siblings)).rstrip("：:").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append({
            "name": name,
            "duty": "",
            "evidence": evidence,
            "detail_url": urljoin(source, str(anchor.get("href") or "")),
            "confidence": "high",
            "parser": "page_inline_jixi_government_leaders_v1",
        })
    return rows


PAGE_RULE = {
    "rule_id": "3847",
    "page_type": "市长卡片与领导列表页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "parser": "page_inline_jixi_government_leaders_v1",
    "leader_region_selector": ".mayor, #tabCon_0 .leadList",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "领导信息分为市长卡片与同一可见列表，需保持其原始展示顺序",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
