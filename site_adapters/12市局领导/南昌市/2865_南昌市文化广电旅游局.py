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
    "rule_id": "2865",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_culture_name_colon_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_nanchang_culture_name_colon_duty_v2",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".list_right .content p",
    "name_selector": "段首冒号前姓名",
    "duty_selector": "段首冒号后职务",
    "detail_link_selector": "",
    "risk_flag": "职务段落后紧随负责、分管事项，仅职务段落可作为依据说明",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = text.replace("\u3000", "")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text.strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析南昌市文化广电旅游局领导分工段落。"""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [_clean_text(node.get_text(" ", strip=True)) for node in soup.select(".list_right .content p")]
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for text in paragraphs:
        match = re.match(r"^([\u4e00-\u9fff]\s*[\u4e00-\u9fff]{1,3})\s*[:：]\s*(.+)$", text)
        if not match:
            continue
        name = _clean_text(match.group(1))
        duty = _clean_text(match.group(2))
        if not name or not duty or len(name) > 4:
            continue
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": page_rule.get("parser", ""),
            }
        )
    if not records:
        raise RuntimeError("领导信息正文未解析出有效的姓名与职务段落")
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
