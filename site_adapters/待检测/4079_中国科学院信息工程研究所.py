from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4079",
    "page_type": "人物表格页",
    "structure_group": "iie_leader_table_duty_name",
    "reuse_scope": "page_structure",
    "load_mode": "动态DOM渲染",
    "extract_mode": "list_direct",
    "parser": "page_inline_iie_leader_table_duty_name",
    "leader_region_selector": ".content, #zoom",
    "risk_flag": "HTTP 响应无有效人物正文，需渲染后解析表格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """读取领导表格中“职务换行姓名”的单元格，按单元格顺序保留原序。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for cell in soup.select("table td"):
        lines = [re.sub(r"\s+", "", text) for text in cell.get_text("\n", strip=True).splitlines()]
        lines = [text for text in lines if text]
        if len(lines) != 2:
            continue
        duty, name = lines
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or not re.search(r"书记|所长|院长|主任|副", duty):
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty})
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
