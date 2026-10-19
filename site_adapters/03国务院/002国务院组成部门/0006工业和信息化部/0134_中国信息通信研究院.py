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
    "rule_id": "0134",
    "page_type": "人物表格页",
    "structure_group": "领导团队表格单元格",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom",
    "collector": "browser_dom",
    "parser": "CaictLeaderTableCellParser_v2",
    "leader_region_selector": "td.main_text_tit",
    "name_selector": "单元格首行",
    "duty_selector": "单元格第二行",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "普通HTTP返回412，必须使用在线浏览器渲染；领导单元格无独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导团队表格单元格DOM顺序抽取姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for cell in soup.select("td.main_text_tit"):
        lines = [_clean_text(line) for line in cell.get_text("\n", strip=True).splitlines()]
        lines = [line for line in lines if line]
        if len(lines) != 2:
            continue
        name, evidence = lines
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "td.main_text_tit；首行姓名；第二行职务",
            }
        )
    if not records:
        raise RuntimeError("领导团队表格未解析到人物记录")
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
