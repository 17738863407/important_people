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
    "rule_id": "4567", "page_type": "省检察院领导图文介绍页",
    "structure_group": "sichuan_procuratorate_person_blocks_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_sichuan_procuratorate_person_blocks_v1",
    "leader_region_selector": "#phone_wz .TRS_Editor", "name_selector": "人物块p > strong",
    "duty_selector": "姓名后以四川省人民检察院开头的p", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析院领导正文人物块；检察委员会委员、专职委员等委员类人物及职务均按网页原序完整保留。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("#phone_wz .TRS_Editor")
    if region is None:
        raise RuntimeError("未找到院领导正文 #phone_wz .TRS_Editor")
    paragraphs = region.find_all("p")
    rows: list[dict[str, str]] = []
    current_name = ""
    evidence_lines: list[str] = []

    def flush() -> None:
        nonlocal current_name, evidence_lines
        if not current_name:
            return
        organization = str(page_rule.get("organization") or "")
        source = next((line for line in evidence_lines if organization and line.startswith(organization)), "")
        if source:
            source = source.rstrip("，,、；;。 ")
            ranks = [line.rstrip("，,") for line in evidence_lines if line and not line.startswith(organization) and any(word in line for word in ("检察官", "监察官", "巡视员"))]
            evidence = "、".join([source, *ranks])
            rows.append({"name": current_name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#phone_wz人物段；完整保留委员与专职委员职务"})
        current_name = ""
        evidence_lines = []

    for paragraph in paragraphs:
        text = compact(paragraph.get_text(" ", strip=True))
        strong = paragraph.find("strong")
        if strong and re.fullmatch(r"[\u3400-\u9fff·]{2,6}", compact(strong.get_text(" ", strip=True))):
            flush()
            current_name = compact(strong.get_text(" ", strip=True))
            continue
        if current_name and text:
            evidence_lines.append(text)
    flush()
    if not rows:
        raise RuntimeError("未提取到省院领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
