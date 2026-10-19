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
    "rule_id": "0312",
    "page_type": "人物列表完整页",
    "structure_group": "中心领导两列表格",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "chrome",
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CpipeLeaderTableParser_v2",
    "leader_region_selector": "div.sub_content table tr",
    "name_selector": "td:nth-of-type(1)",
    "duty_selector": "td:nth-of-type(2)",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP受412限制，需浏览器兜底取得表格；入口页不是人物独立详情页，详情链接必须留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按中心领导表格行顺序抽取姓名与职务单元格。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for row in soup.select("div.sub_content table tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        name = re.sub(r"\s+", "", _clean_text(cells[0].get_text(" ", strip=True)))
        evidence = _clean_text(cells[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(rule.get("parser", "")),
                "selector_summary": "div.sub_content table tr；第1列姓名；第2列职务；按表格行顺序；无个人详情链接",
            }
        )
    if not records:
        raise RuntimeError("中心领导两列表格未解析到人物记录")
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
