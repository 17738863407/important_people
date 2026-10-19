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


PAGE_RULE = {
    "rule_id": "0502",
    "page_type": "人物列表完整页",
    "structure_group": "东海局职务链接姓名列表项",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "EcsMnrLeaderListItemParser_v2",
    "leader_region_selector": ".list_item",
    "name_selector": ".time",
    "duty_selector": ".details",
    "detail_link_selector": ".details[href]",
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "职务链接为独立人物页；必须保留列表职务完整原文，不得删除机构前缀",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按列表项DOM顺序提取姓名、完整职务和独立人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for item in soup.select(".list_item"):
        name_node = item.select_one(".time")
        duty_node = item.select_one(".details")
        if name_node is None or duty_node is None:
            continue
        name = _clean_text(name_node.get_text(" ", strip=True))
        duty = _clean_text(duty_node.get_text(" ", strip=True))
        href = str(duty_node.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(base_url, href) if href else "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".list_item；name=.time；duty/detail=.details[href]",
            }
        )
    if not records:
        raise RuntimeError("领导之窗列表未解析到人物记录")
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
