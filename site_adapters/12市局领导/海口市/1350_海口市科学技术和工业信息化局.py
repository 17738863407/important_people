from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1350", "page_type": "人物简介页",
    "structure_group": "haikou_it_name_profile_current_blocks", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "requests", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "builtin_parse_page", "leader_region_selector": ".content",
    "name_selector": ".content独立姓名段落", "duty_selector": "当前人物基本信息块内现任原句",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "人物简介与长分工连续排列，按独立姓名段开启人物并在分工前提取现任原句",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".content")
    if content is None:
        raise ValueError("页面未发现领导正文.content")
    paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in content.select("p")]
    rows: list[dict[str, str]] = []
    index = 0
    while index < len(paragraphs):
        name = paragraphs[index]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,12}", name):
            index += 1
            continue
        cursor = index + 1
        block: list[str] = []
        while cursor < len(paragraphs):
            part = paragraphs[cursor]
            if part.startswith("分工") or re.fullmatch(r"[\u3400-\u9fff·]{2,12}", part):
                break
            block.append(part)
            cursor += 1
        block_text = "".join(block)
        if "基本信息" in block_text:
            match = re.search(r"(?P<evidence>现任(?P<duty>[^。]+)(?:。|$))", block_text)
            if match:
                rows.append({"name": name, "duty": match.group("duty"),
                             "evidence": match.group("duty"), "detail_url": "",
                             "selector_summary": ".content独立姓名段至分工前基本信息块现任原句"})
        index = max(cursor, index + 1)
    if not rows:
        raise ValueError("领导正文未发现可回指的姓名与现任职务人物块")
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
