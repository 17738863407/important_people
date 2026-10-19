from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3136",
    "page_type": "多人物详情合并页",
    "structure_group": "nanchang_medical_security_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_medical_security_current_sentence_v2",
    "leader_region_selector": ".content",
    "name_selector": ".content p人物简介段首个逗号前",
    "duty_selector": ".content p人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "现任职务与负责或分管信息位于同一句，依据说明必须保留网页完整原句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".content", "row_selector": ".content p"},
        "api": {"enabled": False, "reason": "当前HTTPS正文直接包含按版面顺序排列的人物简介及现任句"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白，不增删原文内容。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按简介段DOM顺序提取姓名和当前段中的完整“现任……”原句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        evidence_match = re.search(r"现任[^。]*(?:。|$)", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        evidence = re.sub(
            r"^现任(?:职务)?(?:\s*[：:]\s*)?\s*",
            "",
            normalize_space(evidence_match.group(0)),
            count=1,
        )
        if name in seen or not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".content p按DOM顺序；简介段首个逗号前姓名；保留同段从现任起至句号或段尾的完整原文",
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
