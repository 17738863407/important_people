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
    "rule_id": "3682", "page_type": "直属单位简介职务姓名段落页",
    "structure_group": "mca_unit_leader_paragraphs_c14507_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "mca_unit_leader_paragraphs_c14507_v1",
    "leader_region_selector": "#zoom", "name_selector": "#zoom p", "duty_selector": "#zoom p", "detail_link_selector": "",
    "content_scope": {"include_selectors": ["#zoom"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 0},
    "risk_flag": "首段为职责，副主任字段一段含两人", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}

def _clean(value: str) -> str:
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", "", value)

def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析#zoom内明确的职务姓名字段段落。"""
    from crawler_core.models import PersonRecord
    region = BeautifulSoup(html, "html.parser").select_one("#zoom")
    if region is None: return []
    rows = []
    for paragraph in region.select("p"):
        match = re.fullmatch(r"([^：:]{2,80})[：:](.+)", _clean(paragraph.get_text(" ", strip=True)))
        if not match: continue
        duties = [_clean(item) for item in re.split(r"[、；;]", match.group(1)) if _clean(item)]
        for name in [_clean(item) for item in re.split(r"[、，,；;]", match.group(2))]:
            if re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
                rows.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name,
                    duty="；".join(duties), detail_url="", evidence="；".join(duties), confidence="high",
                    parser=page_rule["parser"], selector_summary="#zoom内含冒号的职务姓名段落"))
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
