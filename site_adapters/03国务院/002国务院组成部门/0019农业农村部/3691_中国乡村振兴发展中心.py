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
    "rule_id": "3691", "page_type": "无照片领导姓名职务列表页",
    "structure_group": "xczx_no_photo_leader_list_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "xczx_no_photo_leader_list_v1",
    "leader_region_selector": ".ej_ld_nophoto", "name_selector": ".ld_name",
    "duty_selector": ".ld_t dd:first-child", "detail_link_selector": "",
    "content_scope": {"include_selectors": [".ej_ld_nophoto"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "每人第二个dd为主持或分管职责，不能并入职务证据",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def _clean(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """逐个人员li读取姓名与第一个职务dd，排除后续分工说明。"""
    from crawler_core.models import PersonRecord

    region = BeautifulSoup(html, "html.parser").select_one(".ej_ld_nophoto")
    if region is None:
        return []
    rows: list[object] = []
    for item in region.select(":scope > ul > li"):
        name_node = item.select_one(".ld_name")
        duty_node = item.select_one(".ld_t dd")
        name = _clean(name_node.get_text(" ", strip=True)) if name_node else ""
        raw_duty = _clean(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name) or not raw_duty:
            continue
        duties = [_clean(part) for part in re.split(r"[、；;]", raw_duty) if _clean(part)]
        rows.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty="；".join(duties), detail_url="", evidence="；".join(duties), confidence="high",
            parser=page_rule["parser"], selector_summary=".ej_ld_nophoto直属li的姓名与首个dd职务",
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
