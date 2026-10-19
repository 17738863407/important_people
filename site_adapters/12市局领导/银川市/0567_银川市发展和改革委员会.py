from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "0567",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_fgw_merged_profile_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_fgw_merged_profile_blocks_v2",
    "leader_region_selector": ".article .con .view, .con .view",
    "name_selector": "人物块首段姓名",
    "duty_selector": "人物块首段括号职务",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".article .con .view", ".con .view"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "同一正文依次承载多人简历与分工；依据仅取当前人物块内完整现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


HEADER_PATTERN = re.compile(r"^([\u4e00-\u9fff·]{2,8})\s*[（(]([^）)]+)[）)]$")
CURRENT_DUTY_PATTERN = re.compile(r"现\s*任\s*[^。]*。")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """压缩正文中的全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _paragraphs(region: Tag) -> list[str]:
    """按正文段落顺序取得非空文本，保留人物块边界。"""
    values = [_clean_text(node.get_text(" ", strip=True)) for node in region.select("p")]
    return [value for value in values if value]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物标题段划分正文，只在各自人物块内提取现任句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".article .con .view") or soup.select_one(".con .view")
    if region is None:
        return []
    paragraphs = _paragraphs(region)
    headers: list[tuple[int, re.Match[str]]] = []
    for index, paragraph in enumerate(paragraphs):
        match = HEADER_PATTERN.fullmatch(paragraph)
        if match is not None:
            headers.append((index, match))

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for order, (start, match) in enumerate(headers):
        end = headers[order + 1][0] if order + 1 < len(headers) else len(paragraphs)
        name = _clean_text(match.group(1)).replace(" ", "")
        heading_duty = _clean_text(match.group(2))
        block_text = _clean_text(" ".join(paragraphs[start + 1 : end]))
        evidence_match = CURRENT_DUTY_PATTERN.search(block_text)
        evidence = evidence_match.group(0) if evidence_match is not None else heading_duty
        evidence = re.sub(r"^现\s*任\s*", "", evidence).rstrip("。 ")
        if not name or not heading_duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": ".con .view内人物标题段；当前标题至下一标题之间的完整现任句",
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
