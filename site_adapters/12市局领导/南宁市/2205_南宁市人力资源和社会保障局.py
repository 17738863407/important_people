from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2205",
    "page_type": "多人物详情合并页",
    "structure_group": "nanning_hrss_merged_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_hrss_merged_profiles_v2",
    "leader_region_selector": ".trs_editor_view, .TRS_UEDITOR, #UCAP-CONTENT",
    "name_selector": "含现任句简历段中简历标签后首个逗号前",
    "duty_selector": "同一简历段完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "多人简历与工作分工交替，历史固定姓名会保留离任者或遗漏变动；必须动态遍历当前简历段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".trs_editor_view, .TRS_UEDITOR, #UCAP-CONTENT", "name_selector": "简历段首姓名", "duty_selector": "同一简历段完整现任句"},
        "api": {"enabled": False, "reason": "静态合并正文逐人提供简历及现任句"},
    },
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_profile(text: str) -> tuple[str, str]:
    value = normalize_layout(text)
    name_match = re.search(r"(?:简历：)?(?P<name>[\u4e00-\u9fff·]{2,8})，", value)
    evidence_match = re.search(r"现任[^。]*。", value)
    if name_match is None or evidence_match is None:
        return "", ""
    return name_match.group("name"), evidence_match.group(0).removeprefix("现任").removesuffix("。").rstrip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".trs_editor_view, .TRS_UEDITOR, #UCAP-CONTENT")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        name, evidence = parse_profile(paragraph.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "多人简历段按DOM顺序；简历标签后姓名与同段完整现任句"})
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
