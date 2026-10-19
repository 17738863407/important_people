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
    "rule_id": "3935",
    "domain": "zx.hd.gov.cn",
    "page_type": "图片姓名矩阵",
    "structure_group": "handan_cppcc_leader_matrix_2026",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_handan_cppcc_leader_matrix_v1",
    "leader_region_selector": "ul.list_img_main table[height='819']",
    "name_selector": "tr td",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "include_selectors": ["ul.list_img_main"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务由页面标题及首列、中部矩阵、末列的明确版式分组表达，姓名与头像分行排列",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "ul.list_img_main table[height='819']",
            "name_row_selector": "tr:not(:has(img)) td",
        },
        "api": {"enabled": False, "reason": "当前静态HTML表格已表达现任领导姓名及职务分组"},
    },
}


def normalize_name(value: str) -> str:
    """删除姓名单元格中的排版空格。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导姓名矩阵版式顺序解析主席、副主席和秘书长。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("ul.list_img_main table[height='819']")
    if table is None:
        raise RuntimeError("未找到政协领导姓名矩阵 table[height='819']")

    names: list[str] = []
    for row in table.find_all("tr", recursive=False):
        if row.find("img") is not None:
            continue
        for cell in row.find_all("td", recursive=False):
            name = normalize_name(cell.get_text(" ", strip=True))
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                names.append(name)
    if len(names) < 3:
        raise RuntimeError(f"领导姓名矩阵解析数量异常：{len(names)}")

    rows: list[dict[str, str]] = []
    for index, name in enumerate(names):
        duty = "主席" if index == 0 else "秘书长" if index == len(names) - 1 else "副主席"
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导标题 + table[height=819]姓名矩阵；首位主席、中段副主席、末位秘书长",
            }
        )
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
