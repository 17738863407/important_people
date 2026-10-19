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
    "rule_id": "3535",
    "page_type": "人物列表完整页",
    "structure_group": "中国海油公司高层条目",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "CnoocExecutiveHeadingParser_v2",
    "leader_region_selector": "li h3:has(span)",
    "name_selector": "h3 span",
    "duty_selector": "h3 span",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一条目并列集团公司与有限公司职务，仅提取明确以集团公司开头的目标字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u2000-\u200b\u3000]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按公司高层条目顺序提取姓名和集团公司职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for heading in soup.select("li h3:has(span)"):
        values = [_clean_text(node.get_text(" ", strip=True)) for node in heading.select("span")]
        values = [value for value in values if value]
        if len(values) < 2:
            continue
        name = values[0]
        evidence = next((value for value in values[1:] if value.startswith("集团公司")), "")
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
                "selector_summary": "公司高层li条目；h3首个span姓名；集团公司开头span为目标职务",
            }
        )
    if not records:
        raise RuntimeError("中国海油公司高层条目未解析到人物记录")
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
