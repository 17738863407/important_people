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
    "rule_id": "3390", "domain": "zjw.beijing.gov.cn", "page_type": "人物列表完整页",
    "structure_group": "beijing_housing_leader_spans_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct",
    "collector": "static_http", "parser": "page_inline_beijing_housing_leader_spans_v1",
    "risk_flag": "姓名含排版空格；职务限定为ldXm后的同级span", "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for row in soup.select(".lDjSBox p"):
        name_node = row.select_one("span.ldXm")
        duty_node = name_node.find_next_sibling("span") if name_node else None
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        duty = re.sub(r"[（(]挂职[）)]", "", duty).strip("，、；; ")
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or not duty:
            continue
        rows.append({"name": name, "duty": duty, "detail_url": "", "evidence": duty,
                     "confidence": "high", "parser": str(page_rule.get("parser", "")),
                     "selector_summary": "lDjSBox段落ldXm姓名与后续同级span职务"})
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
