from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4573",
    "page_type": "检察院领导分组列表",
    "structure_group": "xinjiang_procuratorate_grouped_lists_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "grouped_lists",
    "parser": "page_xinjiang_procuratorate_grouped_lists_v1",
    "leader_region_selector": ".pagebd .erlist",
    "name_selector": ".erlist li strong",
    "duty_selector": ".erlist li p中的现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "页面用两个同名id分组，后一组为检察委员会专职委员；两个领导分组均按页面原序纳入。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面分组及列表顺序提取现任句，保留专职委员。"""
    soup = BeautifulSoup(html or "", "html.parser")
    items = soup.select(".pagebd .erlist li")
    if not items:
        raise RuntimeError("未找到本院领导分组列表")
    rows: list[dict[str, str]] = []
    for item in items:
        strong = item.find("strong")
        text = re.sub(r"[\s\u00a0\u3000]+", "", item.get_text(" ", strip=True))
        name = re.sub(r"[\s\u00a0\u3000]+", "", strong.get_text(" ", strip=True) if strong else "")
        match = re.search(r"现任([^。]+)", text)
        evidence = match.group(1) if match else ""
        parts = []
        for part in re.split(r"[，,、；;]", evidence):
            if re.search(r"[一二三四五六七八九十]级(?:大检察官|高级检察官|高级监察官)$", part):
                continue
            parts.append(part)
        evidence = "、".join(part for part in parts if part)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name) or not evidence:
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".pagebd .erlist按li原序读取strong姓名和现任句；检察委员会专职委员纳入"})
    if not rows:
        raise RuntimeError("本院领导列表未提取到领导人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
