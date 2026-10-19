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
    "rule_id": "2346",
    "domain": "sgj.jiangxi.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "scoped_biography_paragraph_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_html",
    "parser": "page_inline_scoped_biography_current_sentence_v1",
    "leader_region_selector": "#zoom",
    "person_block_selector": ":scope > p",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物简历与现职同段；必须逐人物段落提取，禁止扫描全页模板文本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩正文中的排版空白，不改写原始现职句。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_current_evidence(value: str) -> str:
    """仅删除已定位现职句句首的“现任”固定标签。"""
    return re.sub(r"^现任(?:职务)?\s*[：:]?\s*", "", value, count=1)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按#zoom直接人物段落顺序提取姓名与完整现任句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in region.find_all("p", recursive=False):
        text = clean_text(node.get_text(" ", strip=True))
        name_match = re.match(r"([\u3400-\u9fff·]{2,5})[，,]", text)
        duty_match = re.search(r"现任[^。]*。", text)
        if name_match is None or duty_match is None:
            continue
        name = name_match.group(1)
        evidence = clean_current_evidence(duty_match.group(0))
        if name in seen:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=#zoom；person=:scope > p；"
                    "name=paragraph prefix before comma；duty=现任[^。]*。"
                ),
            }
        )

    return records


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
