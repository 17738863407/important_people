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
    "rule_id": "3090",
    "domain": "xmy.jl.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "jilin_animal_husbandry_combined_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "combined_profiles",
    "collector": "static_http",
    "parser": "page_inline_jilin_animal_husbandry_combined_profiles_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "增强requests误跳无障碍页；首人物块只有分工和历史履历，无可靠现职依据",
    "confidence": "medium",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def extract_current_duty(block: Tag, organization: str) -> tuple[str, str]:
    """优先提取完整现任句，其次读取人物块中的独立机构职务句。"""
    scope = block.select_one(".TRS_Editor")
    if scope is None:
        return "", ""
    text = clean_text(scope.get_text(" ", strip=True))
    current_match = re.search(r"现任\s*([^。]+)\s*。", text)
    if current_match is not None:
        duty = clean_text(current_match.group(1)).strip("，,。 ")
        return (duty, duty) if duty else ("", "")

    role_pattern = re.compile(
        rf"^{re.escape(organization)}[^。]*(?:书记|局长|副局长|主任|副主任|巡视员)\s*。$"
    )
    for paragraph in scope.select("p"):
        sentence = clean_text(paragraph.get_text(" ", strip=True))
        if role_pattern.fullmatch(sentence):
            duty = sentence.rstrip("。")
            return duty, duty
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按合并页人物块DOM顺序提取姓名及可验证现职依据。"""
    soup = BeautifulSoup(html, "html.parser")
    organization = str(page_rule.get("organization", ""))
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in soup.select(".lmbox > .ldjj"):
        name_node = block.select_one("b > span")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        if not re.fullmatch(r"[\u3400-\u9fff·（）()]{2,16}", name) or name in seen:
            continue
        duty, evidence = extract_current_duty(block, organization)
        seen.add(name)
        records.append(
            {
                "organization": organization,
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": evidence,
                "confidence": "high" if evidence else "low",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=.lmbox>.ldjj；name=b>span；"
                    "duty=profile-current-sentence-or-independent-role-sentence"
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
