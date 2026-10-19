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
    "rule_id": "1701",
    "page_type": "人物表格页",
    "structure_group": "yunnan_mpa_profile_first_rows",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_mpa_profile_first_rows_v1",
    "leader_region_selector": "tr.firstRow",
    "name_selector": "tr.firstRow strong",
    "duty_selector": "tr.firstRow人物简介中性别字段之前文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "首个人物表格首行",
        "end_anchor": "末个人物表格首行",
        "include_selectors": ["tr.firstRow"],
        "exclude_selectors": ["我的分工", "党组成员分工协作关系", "页眉", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "人物简介在姓名后连续包含性别、民族、学历和党派；仅保留性别字段之前的原始职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "tr.firstRow",
            "name_selector": "strong",
            "duty_selector": "同一人物行简介中性别字段之前文本",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "首个人物表格首行",
                "end_anchor": "末个人物表格首行",
                "include_selectors": ["tr.firstRow"],
                "exclude_selectors": ["我的分工", "党组成员分工协作关系", "页眉", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "当前静态HTML人物行已直接提供姓名和职务，页面没有人物详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for person_row in soup.select("tr.firstRow"):
        if _is_hidden(person_row):
            continue
        name = ""
        for strong in person_row.select("strong"):
            candidate = re.sub(r"\s+", "", strong.get_text(" ", strip=True))
            if re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", candidate):
                name = candidate
                break
        if not name or name in seen:
            continue

        duty = ""
        for paragraph in person_row.select("p"):
            profile = _clean_text(paragraph.get_text(" ", strip=True))
            match = re.match(r"^(.*?)[，,]\s*(?:男|女)[，,]", profile)
            if match:
                duty = match.group(1).strip(" ：:，,。. ")
                break
        if not duty:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "custom_yunnan_mpa_profile_first_rows_v1",
                "selector_summary": "tr.firstRow；strong姓名；简介性别字段前职务",
            }
        )
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
