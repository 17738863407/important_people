from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1481",
    "page_type": "多人物详情合并页",
    "structure_group": "nanning_forestry_merged_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_forestry_merged_profiles_v2",
    "leader_region_selector": "#UCAP-CONTENT",
    "name_selector": "含现任句简介段开头至性别字段",
    "duty_selector": "同一简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "多人简介与分工混排且正文含大量字距空白；必须只在各人物简介段内提取姓名和完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#UCAP-CONTENT",
            "name_selector": "含现任句简介段开头至男/女字段",
            "duty_selector": "同一简介段完整现任句",
        },
        "api": {"enabled": False, "reason": "静态合并正文逐人提供简介及现任句"},
    },
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_profile(text: str) -> tuple[str, str]:
    value = normalize_layout(text)
    evidence_match = re.search(r"现任[^。]*。", value)
    if evidence_match is None:
        return "", ""
    prefix = value[: evidence_match.start()]
    name_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})[，,]?\s*[男女](?:，|$)", prefix)
    if name_match is None:
        return "", ""
    evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。")
    return name_match.group("name"), evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#UCAP-CONTENT")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        name, evidence = parse_profile(paragraph.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#UCAP-CONTENT人物简介段按DOM顺序；段首姓名与同段完整现任句",
            }
        )
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
