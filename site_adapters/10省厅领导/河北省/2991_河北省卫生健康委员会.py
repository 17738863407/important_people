from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2991",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "table.ldxx",
    "row_selector": "table.ldxx tr",
    "name_selector": "td:nth-of-type(2)",
    "duty_selector": "td:nth-of-type(2)",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "姓名、职务与人口学信息混排，按每行明确的性别字段边界截取姓名和原始职务。",
}


def normalize_text(text: str) -> str:
    """清理HTML排版空白，保留用于识别字段边界的单个空格。"""
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """从领导信息表格逐行提取姓名与人口学字段之前的原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for row in soup.select("table.ldxx tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue

        text_parts = [normalize_text(text) for text in cells[1].stripped_strings]
        gender_index = next(
            (
                index
                for index, text in enumerate(text_parts)
                if re.match(r"^(?:男|女)[，,]", text)
            ),
            None,
        )
        if gender_index is None:
            continue

        prefix_parts = [part for part in text_parts[:gender_index] if part]
        while prefix_parts and prefix_parts[-1] in {"，", ","}:
            prefix_parts.pop()
        if not prefix_parts:
            continue

        last_part = prefix_parts.pop().rstrip("，,").strip()
        separated = re.match(
            r"^(?P<duty>.+?)\s+(?P<name>[\u4e00-\u9fff·]{2,5})$", last_part
        )
        if separated is not None:
            duty_tail = separated.group("duty")
            name = separated.group("name")
            prefix_parts.append(duty_tail)
        elif re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", last_part):
            name = last_part
        else:
            continue

        duty = "".join(prefix_parts).strip("，,：:；; ")
        if not duty.startswith("河北省卫生健康委员会") or not duty:
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
