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
    "rule_id": "2787",
    "page_type": "多人物详情合并页",
    "structure_group": "leader_heading_and_biography_blocks",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiSportsLeaderHeadingParser_v1",
    "leader_region_selector": "a[href^='javascript']",
    "name_selector": "标题冒号后首个姓名",
    "duty_selector": "标题冒号前完整文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "每个人物标题后含履历与分工，依据只保留标题冒号前完整职务；javascript锚点不是详情页",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """按合并页人物块顺序解析标题中的完整职务和姓名。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        if not str(anchor.get("href", "")).lower().startswith("javascript"):
            continue
        text = _clean_text(anchor.get_text(" ", strip=True))
        match = re.match(r"^(陕西省体育局[^：:]{2,50})[：:]\s*([\u4e00-\u9fff·]{2,8})(?:\s|$)", text)
        if match is None:
            continue
        duty = _clean_text(match.group(1))
        name = re.sub(r"\s+", "", match.group(2))
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
                "selector_summary": "人物javascript锚点；职务=标题冒号前完整文本；姓名=冒号后首个姓名",
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
