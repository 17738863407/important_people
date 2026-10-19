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
    "rule_id": "1588",
    "page_type": "人物列表完整页",
    "structure_group": "中心领导列表p姓名span职务",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MiitecLeaderCardParser_v2",
    "leader_region_selector": "ul.leader.gywmBkx",
    "name_selector": "p",
    "duty_selector": "span",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页另有专家委员会与组织架构，限定中心领导ul",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按中心领导列表DOM顺序抽取姓名和span原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("ul.leader.gywmBkx > li")
    if not items:
        raise RuntimeError("未找到中心领导列表 ul.leader.gywmBkx > li")

    rows: list[dict] = []
    for item in items:
        name_node = item.select_one("p")
        duty_node = item.select_one("span")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "ul.leader.gywmBkx > li；p；span",
            }
        )

    if not rows:
        raise RuntimeError("中心领导列表未解析到姓名职务记录")
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
