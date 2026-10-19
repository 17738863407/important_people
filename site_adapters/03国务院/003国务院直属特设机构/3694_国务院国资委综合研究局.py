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
    "rule_id": "3694", "page_type": "厅局领导同段多字段页", "structure_group": "sasac_department_leaders_n2591482_v1",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "sasac_department_leaders_n2591482_v1",
    "leader_region_selector": ".gywm .bottom dl", "name_selector": "dd p", "duty_selector": "dd p", "detail_link_selector": "",
    "content_scope": {"start_text": "厅局领导", "end_text": "主要职责"},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "局长与副局长写在同一p中，不能按整段单字段解析", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}

def _clean(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value)

def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从厅局领导dl的同一段落依次读取局长、副局长字段。"""
    from crawler_core.models import PersonRecord
    soup = BeautifulSoup(html, "html.parser")
    group = next((dl for dl in soup.select(".gywm .bottom dl") if _clean((dl.select_one("dt") or dl).get_text(" ", strip=True)) == "厅局领导"), None)
    if group is None: return []
    text = _clean(" ".join(node.get_text(" ", strip=True) for node in group.select("dd p")))
    rows = []
    for match in re.finditer(r"(局长|副局长)[：:]([\u3400-\u9fff·]{2,15}?)(?=(?:局长|副局长)[：:]|$)", text):
        rows.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=match.group(2),
            duty=match.group(1), detail_url="", evidence=match.group(1), confidence="high", parser=page_rule["parser"],
            selector_summary="厅局领导dl同一p内按局长/副局长标签顺序"))
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
