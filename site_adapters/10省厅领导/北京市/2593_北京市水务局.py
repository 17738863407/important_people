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
    "rule_id": "2593",
    "domain": "swj.beijing.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "beijing_water_ldjs_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_water_ldjs_cards_v1",
    "risk_flag": "姓名和职务同处ldjs_title，姓名含全角或零宽排版字符",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """删除零宽字符并压缩网页排版空白。"""
    normalized = str(value or "").replace("\u200b", "").replace("\u200d", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片DOM原始顺序读取姓名和同块原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in soup.select(".ldjs_content"):
        title = card.select_one(".ldjs_title")
        name_node = title.select_one("span") if title is not None else None
        if title is None or name_node is None:
            continue
        raw_name = name_node.get_text(" ", strip=True)
        raw_title = title.get_text(" ", strip=True)
        name = re.sub(r"\s+", "", clean_text(raw_name))
        duty = clean_text(raw_title.replace(raw_name, "", 1))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "ldjs_content内ldjs_title姓名span与相邻职务文本",
            }
        )
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
