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
    "rule_id": "3056",
    "domain": "xfj.hunan.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hunan_petition_visible_table_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_hunan_petition_visible_table_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "旧领导行位于HTML注释；职务单元格冒号后为分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """只解析可见表格行，并在结构分隔符处排除工作分工。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in soup.select("table.table > tr"):
        cells = row.select(":scope > td")
        if len(cells) < 2:
            continue
        name = re.sub(r"\s+", "", clean_text(cells[0].get_text(" ", strip=True)))
        duty_and_responsibility = clean_text(cells[1].get_text(" ", strip=True))
        duty = clean_text(re.split(r"[：:]", duty_and_responsibility, maxsplit=1)[0]).rstrip("。")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=table.table > tr；"
                    "fields=td.name + td.zw duty-before-colon；detail=none"
                ),
            }
        )

    return records


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
