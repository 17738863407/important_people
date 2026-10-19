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
    """压缩网页字段的排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按人物块顺序提取链接姓名、全部p职务行和独立详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, block in enumerate(soup.select(".ldy-l-x-r"), start=1):
        link = block.select_one("a[href]")
        name = clean_text(link.get_text(" ", strip=True) if link else "").replace(" ", "")
        duty_parts = [clean_text(node.get_text(" ", strip=True)) for node in block.select("p")]
        duty = "；".join(part for part in duty_parts if part)
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty).strip("；;，, ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href") or "")) if link else "",
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_hainan_drug_leader_blocks_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0084",
    "page_type": "人物列表完整页",
    "structure_group": "海南药监局链接姓名加p职务块",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hainan_drug_leader_blocks_v2",
    "leader_region_selector": ".ldy-l-x-r",
    "name_selector": ".ldy-l-x-r a[href]",
    "duty_selector": ".ldy-l-x-r p",
    "detail_link_selector": ".ldy-l-x-r a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "block_link_only",
        "detail_collector_type": "none",
    },
    "risk_flag": "同一人物可能有多行并列职务，按DOM顺序以分号连接全部p字段，不拼入姓名或其他块",
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
