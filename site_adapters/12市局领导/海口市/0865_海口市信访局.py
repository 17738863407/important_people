from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0865",
    "page_type": "人物简介页",
    "structure_group": "haikou_petition_profile_current_sentence",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".TRS_UEDITOR",
    "name_selector": "基本信息句开头姓名",
    "duty_selector": "同一基本信息句内完整现任句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "基本信息",
        "end_anchor": "相关附件",
        "include_selectors": [".TRS_UEDITOR"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "人物简介与分工连续排列且正文有排版拆词，只在当前基本信息句内提取完整现任原句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".TRS_UEDITOR")
    if content is None:
        raise ValueError("页面未发现领导信息正文容器.TR S_UEDITOR")
    text = compact_text(content.get_text(" ", strip=True))
    pattern = re.compile(
        r"(?P<name>[\u3400-\u9fff·]{2,12})[，,][^。]*?"
        r"(?P<evidence>现任(?P<duty>[^。]+)。)"
    )
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        name = match.group("name")
        duty = match.group("duty")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": ".TRS_UEDITOR当前基本信息句内现任原句",
            }
        )
    if not rows:
        raise ValueError("领导正文未发现可回指的姓名与现任职务基本信息句")
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
