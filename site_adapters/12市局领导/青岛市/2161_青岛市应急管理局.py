from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """只读取当前领导表的姓名和职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.select("table#table5"):
        if "职务" not in table.get_text(" ", strip=True) or "个人简历" not in table.get_text(" ", strip=True):
            continue
        records = []
        for row in table.select("tr"):
            texts = [cell.get_text(" ", strip=True) for cell in row.find_all("td", recursive=False)]
            if "职务" in texts:
                i = texts.index("职务")
                if 0 < i < len(texts) - 1:
                    duty = re.sub(r"\s*([，、；])\s*", r"\1", texts[i + 1])
                    records.append({"name": texts[i - 1], "duty": duty, "detail_url": "", "evidence": duty})
        if records:
            return records
    return []


PAGE_RULE = {
    "rule_id": "2161",
    "page_type": "人物表格页",
    "structure_group": "qingdao_gov_ldxx_table_v1",
    "reuse_scope": "qingdao_government_ldxx_pages",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "S012_qingdao_gov_ldxx_table_v1",
    "leader_region_selector": "table#table5",
    "detail_strategy": {
        "required": False,
        "mode": "none",
    },
    "risk_flag": "同页后续包含内设机构信息；仅解析带有职务与个人简历标签的table5领导表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
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
