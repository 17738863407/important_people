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
    "rule_id": "2415",
    "page_type": "人物表格页",
    "structure_group": "leader_name_colon_duty_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiCaLeaderParagraphParser_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "#zoom p冒号前文本",
    "duty_selector": "#zoom p冒号后文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "当前响应已静态直出局领导正文，无需快照或浏览器DOM",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按正文段落顺序解析“姓名：职务”。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#zoom")
    if scope is None:
        return []
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in scope.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})\s*[：:]\s*(.+)", text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = _clean_text(match.group(2))
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "#zoom p；姓名=冒号前文本；职务=冒号后文本",
                "order": str(len(records) + 1),
            }
        )
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
