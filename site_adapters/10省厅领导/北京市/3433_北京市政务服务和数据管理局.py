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


PAGE_RULE = {
    "rule_id": "3433", "domain": "zwfwj.beijing.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "beijing_data_bureau_lead_info_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_beijing_data_bureau_lead_info_v1",
    "risk_flag": "每项含姓名段和明确职务标签段；证据须保留原始职务段，不拼接姓名",
    "confidence": "high", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for item in soup.select("li.lead_info"):
        paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in item.select("p")]
        name = next((text for text in paragraphs if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", text)), "")
        evidence = next((text for text in paragraphs if re.match(r"^职\s*务\s*[:：]", text)), "")
        duty = re.sub(r"^职\s*务\s*[:：]\s*", "", evidence).strip()
        if not name or not duty:
            continue
        duty = re.sub(r"[（(]\s*(?:兼|挂职|主持(?:日常)?工作)\s*[）)]", "", duty).strip(" ，,；;")
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty,
                     "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "lead_info姓名段与职务标签段"})
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
