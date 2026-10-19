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
    "rule_id": "3536",
    "page_type": "人物列表完整页",
    "structure_group": "中国石油集团高层条目",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CnpcLeaderColumnParser_v2",
    "leader_region_selector": ".content .column1:has(.text1-1), .content .column2:has(.text1-1)",
    "name_selector": ".text1-1",
    "duty_selector": ".text1-2",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "HTTP请求返回412；同一条目并列集团公司与股份公司职务，仅取目标集团字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2000-\u200b\u3000]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按集团高层条目顺序提取姓名和集团公司职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    selector = ".content .column1:has(.text1-1), .content .column2:has(.text1-1)"
    for card in soup.select(selector):
        name_node = card.select_one(".text1-1")
        if name_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        duties = [_clean_text(node.get_text(" ", strip=True)) for node in card.select(".text1-2")]
        evidence = next((duty for duty in duties if duty.startswith("集团公司")), "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "集团高层column条目；text1-1姓名；集团公司开头text1-2为目标职务",
            }
        )
    if not records:
        raise RuntimeError("中国石油集团高层条目未解析到人物记录")
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
