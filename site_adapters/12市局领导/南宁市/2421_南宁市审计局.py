from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2421",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_audit_title_division_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_audit_title_division_v2",
    "leader_region_selector": "#UCAP-CONTENT",
    "name_selector": "姓名职务短标题段首个空白前",
    "duty_selector": "同一短标题段完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "姓名职务短标题段与分工、联系区域交替；必须只接受空白分隔且含明确领导职务词的短标题段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "#UCAP-CONTENT", "name_selector": "短标题段首个空白前", "duty_selector": "同一短标题段完整原文"}, "api": {"enabled": False, "reason": "静态正文按姓名职务标题与分工段交替展示"}},
}


def normalize_title(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_title(text: str) -> tuple[str, str]:
    value = normalize_title(text)
    if not value or len(value) > 100:
        return "", ""
    match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})\s+(?P<duty>.+)", value)
    if match is None or re.search(r"(?:书记|主任|局长|副局长|调研员)", match.group("duty")) is None:
        return "", ""
    return match.group("name"), match.group("duty")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#UCAP-CONTENT")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        name, evidence = parse_title(paragraph.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#UCAP-CONTENT姓名职务短标题段按DOM顺序；保留同一标题段原文"})
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
