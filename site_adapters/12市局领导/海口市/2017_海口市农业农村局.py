from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2017", "page_type": "人物简介页",
    "structure_group": "haikou_agriculture_name_current_blocks", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "requests", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "builtin_parse_page", "leader_region_selector": ".TRS_UEDITOR",
    "name_selector": "各人物头像后的首个姓名短职务标题", "duty_selector": "当前头像块完整现任原句", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "姓名与短职务同段且简介和长分工连续混排，按人物头像至下一头像边界提取首标题和现任原句",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".TRS_UEDITOR")
    if content is None:
        raise ValueError("页面未发现领导正文.TR S_UEDITOR")
    rows: list[dict[str, str]] = []
    for image in content.select("img"):
        anchor = image.find_parent("p")
        if anchor is None:
            continue
        block: list[str] = []
        for paragraph in anchor.find_all_next("p"):
            if content not in paragraph.parents:
                break
            if paragraph.select_one("img") is not None:
                break
            text = compact_text(paragraph.get_text(" ", strip=True))
            if text:
                block.append(text)
        if not block:
            continue
        heading_match = re.match(
            r"^(?P<name>[\u3400-\u9fff·]{2,4})(?=党组|[一二三四]级调研员)",
            block[0],
        )
        duty_match = re.search(r"(?P<evidence>现任(?P<duty>[^。]+)。)", "".join(block))
        if not heading_match or not duty_match:
            continue
        duty = re.sub(r"[（(]\s*兼\s*[)）]", "", duty_match.group("duty")).strip(" 、，")
        rows.append({"name": heading_match.group("name"), "duty": duty,
                     "evidence": duty, "detail_url": "",
                     "selector_summary": ".TRS_UEDITOR人物头像至下一头像块首标题与完整现任原句"})
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
