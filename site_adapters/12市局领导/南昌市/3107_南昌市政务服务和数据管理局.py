from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3107",
    "page_type": "领导信息正文页",
    "structure_group": "nanchang_government_service_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_government_service_current_sentence_v2",
    "leader_region_selector": "#zoomcon",
    "name_selector": "#zoomcon内人物块姓名标题",
    "duty_selector": "同一人物块内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "正文同时包含简介、现任职务和分工，必须限制在当前人物块的现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": "#zoomcon", "row_selector": "不含嵌套p或div的正文叶块"},
        "api": {"enabled": False, "reason": "当前HTTPS正文直接包含姓名标题及可逐字定位的现任职务句"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按正文人物标题顺序提取各自内容块中的完整“现任……”句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#zoomcon")
    if region is None:
        return []

    blocks = [
        normalize_space(element.get_text(" ", strip=True))
        for element in region.find_all(["p", "div"])
        if element.find(["p", "div"]) is None
    ]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    index = 0
    while index < len(blocks):
        heading = blocks[index]
        heading_match = re.match(r"^(?P<name>[\u4e00-\u9fff· ]{2,12})\s*[：:]", heading)
        if heading_match is None:
            index += 1
            continue
        name = re.sub(r"\s+", "", heading_match.group("name"))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            index += 1
            continue

        next_index = index + 1
        evidence = ""
        while next_index < len(blocks):
            if re.match(r"^[\u4e00-\u9fff· ]{2,12}\s*[：:]", blocks[next_index]):
                break
            current_match = re.search(r"现任[^。]*。", blocks[next_index])
            if current_match is not None:
                evidence = normalize_space(current_match.group(0)).removeprefix("现任").removesuffix("。")
                evidence = re.sub(r"[（(]\s*挂职\s*[）)]", "", evidence).strip(" ，,")
                break
            next_index += 1
        if evidence and name not in seen:
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": "",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "#zoomcon正文叶块按DOM顺序；姓名标题至下一姓名标题为当前人物块；仅提取块内完整现任句",
                }
            )
        index = max(index + 1, next_index)
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
