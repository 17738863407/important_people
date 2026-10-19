from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3135",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_medical_security_division_notice_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_medical_security_division_notice_v2",
    "leader_region_selector": ".content",
    "name_selector": "姓名 市医疗保障局职务标题段姓名",
    "duty_selector": "标题段及紧邻非职责续行原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "少数长职务跨到下一段；只允许合并紧邻且不以主持、负责、分管、协助开头的短续行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".content", "name_selector": "姓名 市医疗保障局标题段", "duty_selector": "标题段及合法紧邻续行"}, "api": {"enabled": False, "reason": "工作分工通知正文静态列出姓名与职务"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = [normalize_layout(p.get_text(" ", strip=True)) for p in soup.select(".content p")]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, text in enumerate(paragraphs):
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff· ]{2,12}?)\s+(?P<duty>市医疗保障局.+)", text)
        if match is None:
            continue
        name = match.group("name").replace(" ", "")
        duty = match.group("duty")
        if index + 1 < len(paragraphs):
            continuation = paragraphs[index + 1]
            if continuation and len(continuation) <= 80 and re.match(r"(?:主持|负责|分管|协助|联系|南宁市医疗保障局|[\u4e00-\u9fff·]{2,8} 市医疗保障局)", continuation) is None:
                duty += continuation
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": ".content姓名职务标题段按DOM顺序；仅合并紧邻非职责短续行"})
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
