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
    "rule_id": "4558", "page_type": "省高级法院人员信息页",
    "structure_group": "shandong_high_court_role_name_lines_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_shandong_high_court_role_name_lines_v1",
    "leader_region_selector": "#con_one_1 .nrCont", "name_selector": "法院职务行冒号后姓名",
    "duty_selector": "法院职务行冒号前文本", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅解析院领导正文中的法院职务行；审判委员会专职审判委员等委员类条目同样保留。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("#con_one_1 .nrCont")
    if region is None:
        raise RuntimeError("未找到院领导正文 #con_one_1 .nrCont")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in region.find_all(["p", "div"], recursive=True):
        if node.find(["p", "div"], recursive=False):
            continue
        text = compact(node.get_text(" ", strip=True))
        match = re.fullmatch(r"(山东省高级人民法院.+?)[：:]([\u3400-\u9fff·]{2,6})", text)
        if not match:
            continue
        evidence, name = match.groups()
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#con_one_1 .nrCont院领导职务行；冒号拆分；委员条目同样保留"})
    if not rows:
        raise RuntimeError("未提取到法院领导区域人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
