from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1116",
    "page_type": "多人物详情合并页",
    "structure_group": "nanchang_jgj_merged_current_profile_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_jgj_merged_current_profile_v1",
    "leader_region_selector": ".xxgk-container:nth-of-type(3) p",
    "name_selector": "人物简介段落开头、首个逗号之前",
    "duty_selector": "同一人物段落中的完整“现任……”句",
    "detail_link_selector": "",
    "risk_flag": "每人简介后紧随分工段落，仅抽取当前简介内部的现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理正文中的全角、半角排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐段解析合并页面中的人物姓名与完整现任职务句。"""
    del final_url
    if not str(html or "").strip():
        raise RuntimeError("在线入口返回空页面")

    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(".xxgk-container:nth-of-type(3)") or soup
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in main.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})[，,]", text)
        duty_match = re.search(r"(?P<evidence>现任(?P<duty>[^。]+)。)", text)
        if not name_match or not duty_match:
            continue
        name = name_match.group("name")
        duty = duty_match.group("duty")
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_nanchang_jgj_merged_current_profile_v1",
                "selector_summary": "leader=.xxgk-container:nth-of-type(3) p；name=段首；duty=同段现任句；detail=none",
            }
        )
    if not rows:
        raise RuntimeError("未从多人物领导正文中提取到有效现任职务")
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
