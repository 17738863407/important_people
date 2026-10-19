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
    "rule_id": "3677", "page_type": "机构简介内领导字段段落页",
    "structure_group": "neac_museum_profile_leader_paragraphs_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "neac_museum_profile_leader_paragraphs_v1",
    "leader_region_selector": ".p3", "name_selector": ".p3 p", "duty_selector": ".p3 p",
    "detail_link_selector": "", "content_scope": {"start_text": "单位领导", "end_text": "内设部门"},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "字段内存在异常字距与顿号后空格，须在单位领导和内设部门标题间严格截断",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """只解析单位领导小节中的职务姓名字段。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    active = False
    rows: list[object] = []
    for paragraph in soup.select(".p3 p"):
        text = _clean(paragraph.get_text(" ", strip=True))
        if text == "单位领导":
            active = True
            continue
        if text == "内设部门":
            break
        if not active:
            continue
        match = re.fullmatch(r"([^：:]+)[：:]([\u3400-\u9fff·]{2,15})", text)
        if not match:
            continue
        duties = [_clean(item) for item in re.split(r"[、；;]", match.group(1)) if _clean(item)]
        rows.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=match.group(2),
            duty="；".join(duties), detail_url="", evidence="；".join(duties), confidence="high",
            parser=page_rule["parser"], selector_summary=".p3内单位领导至内设部门之间的职务：姓名段落",
        ))
    return rows


def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
