from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4561",
    "page_type": "省级检察院领导履历列表",
    "structure_group": "shanxi_procuratorate_biography_cells_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_shanxi_procuratorate_biography_cells_v1",
    "leader_region_selector": "td.b16.hg190",
    "name_selector": "履历正文句首姓名",
    "duty_selector": "履历正文现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "现任句常同时含检察委员会委员；领导履历中的委员类职务及仅任专职委员者全部保留。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    for cell in soup.select("td.b16.hg190"):
        text = re.sub(r"[\s\u200b\u3000\xa0]+", "", cell.get_text(" ", strip=True))
        name_match = re.match(r"([\u3400-\u9fff·]{2,10})，", text)
        duty_match = re.search(r"现任(.+?)(?:。|$)", text)
        if name_match is None or duty_match is None:
            continue
        parts = [part.strip() for part in re.split(r"[、；;]", duty_match.group(1)) if part.strip()]
        duty = "、".join(parts)
        # 人物容器与“现任”句已经构成强结构，不能再用职务关键词二次筛选，
        # 否则页面后部仅任检察委员会专职委员的人员会被误删。
        if not duty:
            continue
        rows.append({
            "name": name_match.group(1), "duty": duty, "evidence": duty, "detail_url": "",
            "confidence": "high", "parser": str(page_rule.get("parser", "")),
            "selector_summary": "td.b16.hg190履历；句首姓名；现任句；保留全部委员职务",
        })
    if not rows:
        raise RuntimeError("领导履历未提取到领导人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
