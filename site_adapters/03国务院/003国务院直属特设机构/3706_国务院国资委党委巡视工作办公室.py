from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3706", "page_type": "共享厅局领导模块分小节页", "structure_group": "sasac_inspection_office_section_v1",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "sasac_inspection_office_section_v1",
    "leader_region_selector": ".gywm .bottom dl", "name_selector": "dd p", "duty_selector": "dd p", "detail_link_selector": "",
    "content_scope": {"start_text": "党委巡视工作办公室", "end_text": "国资委巡视组"},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "同一厅局领导dl同时包含巡视办公室和巡视组，必须按strong小节标题严格截断", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}

def _clean(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value)

def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """只解析党委巡视工作办公室小节，遇国资委巡视组标题即停止。"""
    from crawler_core.models import PersonRecord
    soup = BeautifulSoup(html, "html.parser")
    group = next((dl for dl in soup.select(".gywm .bottom dl") if _clean((dl.select_one("dt") or dl).get_text(" ", strip=True)) == "厅局领导"), None)
    if group is None: return []
    active = False
    rows = []
    for node in group.select("dd > p"):
        text = _clean(node.get_text(" ", strip=True))
        if text == "党委巡视工作办公室": active = True; continue
        if text == "国资委巡视组": break
        if not active: continue
        match = re.fullmatch(r"([^：:]{2,40})[：:](.+)", text)
        if not match: continue
        duty = match.group(1)
        for name in re.split(r"[、，,；;]", match.group(2)):
            if re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                rows.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name,
                    duty=duty, detail_url="", evidence=duty, confidence="high", parser=page_rule["parser"],
                    selector_summary="厅局领导dl内党委巡视工作办公室小节"))
    return rows

def main(update_fetch_memory: bool) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=update_fetch_memory)
    print(f"输出文件：{output_path}")

if __name__ == "__main__":
    update_fetch_memory = False
    main(update_fetch_memory)
