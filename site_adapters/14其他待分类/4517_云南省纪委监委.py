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
    "rule_id": "4517",
    "page_type": "纪委监委段落职务名单",
    "structure_group": "yunnan_discipline_supervision_paragraph_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "role_sections",
    "parser": "page_yunnan_discipline_supervision_paragraph_groups_v1",
    "leader_region_selector": ".zwgk_right .content",
    "name_selector": "职务标题后的相邻p",
    "duty_selector": "p > strong",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "同页含纪委委员与监委委员完整名单；仅解析书记、副书记、常委、主任、副主任分组。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按机构标题及后续职务段落原序提取，并合并同人纪委、监委任职。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".zwgk_right .content")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .zwgk_right .content")
    allowed = {"书记", "副书记", "常务委员会委员", "主任", "副主任"}
    subject = ""
    role = ""
    order: list[str] = []
    duties: dict[str, list[str]] = {}
    for paragraph in region.find_all("p", recursive=False):
        text = paragraph.get_text(" ", strip=True)
        compact = re.sub(r"\s+", "", text)
        if compact.startswith("中国共产党云南省") and compact.endswith("纪律检查委员会"):
            subject, role = compact, ""
            continue
        if compact == "云南省监察委员会":
            subject, role = compact, ""
            continue
        strong = paragraph.find("strong")
        if strong is not None:
            candidate = re.sub(r"\s+", "", strong.get_text(" ", strip=True))
            role = candidate if candidate in allowed else ""
            continue
        if not subject or not role:
            continue
        raw = paragraph.get_text("", strip=False)
        for token in re.split(r"\u00a0+|[ \t]{2,}", raw):
            name = re.sub(r"（[^）]*）", "", token)
            name = re.sub(r"[\s\u00a0\u3000]+", "", name)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                continue
            if name not in duties:
                duties[name] = []
                order.append(name)
            evidence = f"{subject}{role}"
            if evidence not in duties[name]:
                duties[name].append(evidence)
    rows = [{"name": name, "duty": "；".join(duties[name]), "evidence": "；".join(duties[name]), "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".zwgk_right .content内按机构标题、strong职务及相邻p解析；委员分组排除；同人按首次出现合并"} for name in order]
    if not rows:
        raise RuntimeError("领导机构正文未提取到允许职务人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
