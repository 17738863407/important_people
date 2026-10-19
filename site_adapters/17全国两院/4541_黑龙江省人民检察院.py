from __future__ import annotations
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\\s\\u3000\\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4541", "page_type": "省级检察院领导履历列表",
    "structure_group": "heilongjiang_procuratorate_biography_cells_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_heilongjiang_procuratorate_biography_cells_v1",
    "leader_region_selector": "td.b16.hg190",
    "name_selector": "履历正文句首姓名", "duty_selector": "履历正文现任句",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "院领导及页面下方检委会专职委员、省管干部均使用同一履历单元格结构；按全部履历单元格的网页顺序提取并保留现任句中的全部职务。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    for cell in soup.select("td.b16.hg190"):
        text = clean(cell.get_text(" ", strip=True))
        name_match = re.match(r"([\u3400-\u9fff·]{2,10})，", text)
        duty_match = re.search(r"现任(.+?)(?:。|$)", text)
        if name_match is None or duty_match is None:
            continue
        parts = [part for part in re.split(r"[、；;]", duty_match.group(1)) if part]
        duty = "、".join(parts)
        if not duty:
            continue
        rows.append({
            "name": name_match.group(1), "duty": duty, "evidence": duty, "detail_url": "",
            "confidence": "high", "parser": str(page_rule.get("parser", "")),
            "selector_summary": "全部td.b16.hg190履历按DOM原序提取；句首姓名；现任句；包含页面下方检委会专职委员、省管干部分组",
        })
    if not rows:
        raise RuntimeError("领导履历单元格未提取到领导人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
