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
    "rule_id": "4533", "page_type": "省检察院领导图文介绍页",
    "structure_group": "guizhou_procuratorate_strong_pairs_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_guizhou_procuratorate_strong_pairs_v1",
    "leader_region_selector": ".trs_editor_view", "name_selector": "领导及专职委员分组人物姓名strong",
    "duty_selector": "姓名后领导职务strong", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "解析省院领导及检察委员会专职委员两个领导分组，按正文原序保留全部人物。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = next((node for node in soup.select(".trs_editor_view") if "一、贵州省人民检察院领导" in node.get_text("", strip=True)), None)
    if region is None:
        raise RuntimeError("未找到领导介绍正文 .trs_editor_view")
    rows: list[dict[str, str]] = []
    pending_name = ""
    for node in region.find_all(["p", "strong"]):
        if node.name == "p" and node.find_parent("p") is not None:
            continue
        text = compact(node.get_text(" ", strip=True))
        if node.name != "strong":
            continue
        if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", text):
            pending_name = text
            continue
        if pending_name and "贵州省人民检察院" in text:
            evidence = re.sub(r"[，,]", "、", text)
            rows.append({"name": pending_name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": ".trs_editor_view领导及专职委员分组strong姓名—职务配对"})
            pending_name = ""
    if not rows:
        raise RuntimeError("未提取到省院领导区域人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
