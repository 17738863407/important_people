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
    "rule_id": "2163",
    "page_type": "人物表格页",
    "structure_group": "qingdao_gov_ldxx_table_v1",
    "reuse_scope": "qingdao_government_ldxx_pages",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "S012_qingdao_gov_ldxx_table_v1",
    "leader_region_selector": "table#table5",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页后续包含内设机构信息；仅解析带有职务与个人简历标签的table5领导表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一网页字段的确定性排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在含个人简历的领导表中配对姓名、职务标签和职务单元格。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for table in soup.select("table#table5"):
        if "个人简历" not in table.get_text(" ", strip=True):
            continue
        for tr in table.select("tr"):
            cells = tr.select(":scope > td")
            if len(cells) < 3 or _clean_text(cells[1].get_text(" ", strip=True)) != "职务":
                continue
            name = re.sub(r"\s+", "", _clean_text(cells[0].get_text(" ", strip=True)))
            evidence = _clean_text(cells[2].get_text(" ", strip=True))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not evidence or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": ""})
    if not rows:
        raise RuntimeError("未找到含个人简历的领导表职务行")
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
