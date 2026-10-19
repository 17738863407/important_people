from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0991",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "body > table",
    "row_selector": "仅含一张人物图片的最小table",
    "name_selector": "人物表格strong或b的最后一行",
    "duty_selector": "人物表格strong或b中姓名前文本",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "页面使用多层嵌套table，外层表格会重复包含全部人物；只解析恰含一张图片的最小人物表格。历史分工链接仅存在于HTML注释。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按最小人物表格的DOM顺序提取职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for table in soup.select("table"):
        if len(table.select("img")) != 1:
            continue
        label = table.select_one("td div[align='center'] strong, td div[align='center'] b")
        if label is None:
            continue
        parts = [normalize_text(text) for text in label.stripped_strings if normalize_text(text)]
        if len(parts) < 2:
            continue
        name = parts[-1]
        duty = "".join(parts[:-1]).strip("：:，,。；; ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
            }
        )

    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
