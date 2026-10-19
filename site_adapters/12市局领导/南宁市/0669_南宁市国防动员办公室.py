from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0669",
    "page_type": "多人物详情合并页",
    "structure_group": "nanning_national_defense_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_static_http",
    "parser": "page_nanning_national_defense_profile_v2",
    "leader_region_selector": ".TRS_Editor.article-content",
    "name_selector": "姓名简介标题段",
    "duty_selector": "紧随简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "姓名简介标题与任职简介分处相邻段落，姓名含版面字距空白，必须保持标题顺序配对",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".TRS_Editor.article-content", "row_selector": ".TRS_Editor.article-content p"},
        "api": {"enabled": False, "reason": "多人物简介正文由静态HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按姓名简介标题顺序配对后续简介中的完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_Editor.article-content")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    current_name = ""
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        name_match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,8})简介：", text)
        if name_match is not None:
            current_name = name_match.group("name")
            continue
        evidence_match = re.search(r"现任[^。]*。", text)
        if not current_name or evidence_match is None:
            continue
        if current_name not in seen:
            evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).rstrip("。")
            seen.add(current_name)
            rows.append(
                {
                    "name": current_name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".TRS_Editor.article-content p按DOM顺序；姓名简介标题与后续含完整现任句的简介段配对",
                }
            )
        current_name = ""
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
