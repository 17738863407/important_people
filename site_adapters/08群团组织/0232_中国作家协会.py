from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0232",
    "page_type": "人物列表完整页",
    "structure_group": "中国作协主席、副主席与书记处书记",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_chinawriter_present_leaders_v2",
    "leader_region_selector": "div.present",
    "name_selector": "h3.present_item + div.present_info div.item",
    "duty_selector": "h3.present_item",
    "detail_link_selector": "",
    "risk_flag": "同页含主席团委员和全国委员会委员，按分组标题排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def split_name_note(value: str) -> tuple[str, str]:
    """拆分姓名后的明确工作备注。"""
    text = clean_text(value)
    note_match = re.search(r"[（(]([^）)]+)[）)]", text)
    note = clean_text(note_match.group(1)) if note_match else ""
    name = clean_text(re.sub(r"[（(][^）)]*[）)]", "", text))
    return name, note


def target_section(heading: str) -> bool:
    """仅接收主席、副主席和书记处书记三个目标分组。"""
    if "主席团委员" in heading or "全国委员会委员" in heading:
        return False
    return any(label in heading for label in ("委员会主席", "委员会副主席", "书记处书记"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按网页分组顺序解析中国作协现任领导。"""
    soup = BeautifulSoup(html, "html.parser")
    present = soup.select_one("div.present")
    if not isinstance(present, Tag):
        raise RuntimeError("未定位到中国作协领导分组区")

    order: list[str] = []
    duties: dict[str, list[str]] = {}
    for heading_node in present.select("h3.present_item"):
        heading = clean_text(heading_node.get_text(" ", strip=True))
        if not target_section(heading):
            continue
        evidence_heading = re.sub(
            r"\s*[（(]\s*按姓氏笔画为序\s*[）)]",
            "",
            heading,
        ).strip()
        info = heading_node.find_next_sibling("div", class_="present_info")
        if not isinstance(info, Tag):
            continue
        for item in info.select("div.item"):
            raw_name = clean_text(item.get_text(" ", strip=True))
            if raw_name in {"prev", "next"}:
                continue
            name, _note = split_name_note(raw_name)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                continue
            evidence = evidence_heading
            if name not in duties:
                order.append(name)
                duties[name] = []
            if evidence not in duties[name]:
                duties[name].append(evidence)

    if not order:
        raise RuntimeError("中国作协目标领导分组未抽取到人物")

    return [
        {
            "organization": page_rule["organization"],
            "url": page_rule["url"],
            "name": name,
            "duty": "；".join(duties[name]),
            "detail_url": "",
            "evidence": "；".join(duties[name]),
            "confidence": "high",
            "parser": "page_inline_chinawriter_present_leaders_v2",
            "selector_summary": (
                "strategy=custom_parse_page；scope=div.present；"
                "include=主席/副主席/书记处书记；exclude=主席团委员/全国委员会委员"
            ),
        }
        for name in order
    ]


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
