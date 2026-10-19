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
    "rule_id": "0147",
    "page_type": "多人物详情合并页",
    "structure_group": "院领导简介块",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CcidGroupLeaderProfileBlockParser_v2",
    "leader_region_selector": ".plist1",
    "name_selector": "h2",
    "duty_selector": "h3",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "简介块含大量历任经历，必须只使用h2姓名与h3当前职务；历史动态命名保留以维持同名输出",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按院领导简介块DOM顺序抽取姓名与h3完整职务原文。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for block in soup.select(".plist1"):
        name_node = block.select_one("h2")
        duty_node = block.select_one("h3")
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        evidence = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".plist1；h2姓名；h3完整当前职务",
            }
        )
    if not records:
        raise RuntimeError("院领导简介块未解析到人物记录")
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
