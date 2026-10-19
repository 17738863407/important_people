from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4215",
    "page_type": "理事会理事与监事名单页",
    "structure_group": "cdrf_board_and_supervisors",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "page_inline_cdrf_board_v1",
    "leader_region_selector": ".about-us-right-brief",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时列出理事和监事；按两个名单标题切换职务，不把成员简介中的外部任职替代其名单身份。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按网页顺序提取第五届理事会理事、监事及页面明确写出的基金会内部职务。"""
    from bs4 import BeautifulSoup, Tag

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".about-us-right-brief")
    if not isinstance(region, Tag):
        raise RuntimeError("官网未提供理事会名单正文容器")

    rows: list[dict] = []
    current_duty = ""
    for paragraph in region.find_all("p"):
        raw_text = paragraph.get_text(" ", strip=True)
        compact = re.sub(r"\s+", "", raw_text)
        if "第五届理事会理事名单" in compact:
            current_duty = "理事"
            continue
        if "第五届理事会监事名单" in compact:
            current_duty = "监事"
            continue
        if not current_duty or not raw_text or "以姓氏笔画为序" in compact:
            continue

        name = ""
        for boundary in re.finditer(r"\s+", raw_text):
            candidate = re.sub(r"\s+", "", raw_text[: boundary.start()])
            if re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", candidate):
                name = candidate
                break
        if not name:
            continue

        specific_duty = re.search(r"中国发展研究基金会([^，。；\s]+)", compact)
        duty = f"中国发展研究基金会{specific_duty.group(1)}" if specific_duty else current_duty
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})

    if len(rows) != 22:
        raise RuntimeError(f"官网第五届理事会名单应为17名理事和5名监事，当前解析到{len(rows)}人")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
