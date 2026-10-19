from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """压缩页面字段中的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从司法厅领导列表中限定提取监狱管理局负责人。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, item in enumerate(soup.select(".leadercon li"), start=1):
        name_link = item.select_one("div p:first-of-type a[href]")
        duty_node = item.select_one("a.name")
        name = clean_text(name_link.get_text(" ", strip=True) if name_link else "").replace(" ", "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if "监狱管理局" not in duty:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(name_link.get("href") or "")) if name_link else "",
                "source_order": str(source_order),
                "confidence": "high",
                "parser": "page_inline_hainan_prison_from_justice_leaders_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1270",
    "page_type": "人物列表完整页",
    "structure_group": "海南司法厅领导列表中的监狱管理局负责人",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hainan_prison_from_justice_leaders_v2",
    "leader_region_selector": ".leadercon li",
    "name_selector": "div p:first-of-type a[href]",
    "duty_selector": "a.name",
    "detail_link_selector": "div p:first-of-type a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "filtered_list_link",
        "detail_collector_type": "none",
    },
    "risk_flag": "入口同时列出司法厅全体领导，仅保留原始职务字段明确包含监狱管理局的人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
