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
    "rule_id": "3722", "page_type": "单人简介页", "structure_group": "xinhua_press_single_profile_v1", "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "detail_direct", "collector": "static_http", "parser": "page_inline_xinhua_press_single_profile_v1",
    "leader_region_selector": "#content", "name_selector": "#content p", "duty_selector": "#content p span span", "detail_link_selector": "",
    "content_scope": {"start_anchor": "新华出版社有限责任公司", "end_anchor": "曾任", "include_selectors": ["#content"], "exclude_selectors": ["script", "style"]}, "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "单人简介正文后续包含大量曾任职务，必须只解析首个同时含公司名和当前职务内层span的段落；专业技术职称不作为公司领导职务", "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "page_inline_current_profile_sentence",
    "locator": {"css": {"container_selector": "#content", "row_selector": "p", "duty_selector": "p span span"}, "api": {"enabled": False, "reason": "原始HTML简介首段明确标出姓名和现任公司职务"}, "migration": {"source": "new_verified_online", "verified_status": "verified_current_online"}},
}


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#content")
    if container is None:
        return []
    for paragraph in container.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if "新华出版社有限责任公司" not in text or text.startswith("曾任"):
            continue
        match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        duty_node = paragraph.select_one("span span")
        if match is None or duty_node is None:
            continue
        duty = clean_text(duty_node.get_text(" ", strip=True)).replace("、", "；")
        if not duty:
            continue
        return [{"name": match.group("name"), "duty": duty, "detail_url": "", "source_text": duty, "method": page_rule["parser"], "note": "strategy=custom_parse_page；scope=current_profile_first_paragraph；clean=multi_duty_delimiter"}]
    return []


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
