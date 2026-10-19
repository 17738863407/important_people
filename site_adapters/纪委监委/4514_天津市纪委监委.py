from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4514",
    "page_type": "纪委监委同页分段领导机构",
    "structure_group": "tianjin_discipline_supervision_segmented_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_tianjin_discipline_supervision_segmented_v1",
    "leader_region_selector": ".z-page-inner",
    "name_selector": "允许角色标签所在p及其后续无标签p",
    "duty_selector": ".z-page-inner p > strong",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "常务委员会委员姓名跨两个后续段落；仅保留纪委书记、副书记、常务委员会委员及监委主任、副主任，遇委员标签立即停止当前角色，排除委员名单。",
}


def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").rstrip("：:")


def extract_names(value: str) -> list[str]:
    cleaned = re.sub(r"（[^）]*）|\([^)]*\)", "", value or "").strip(" ：:")
    tokens = [part.strip("，,、；;：:") for part in re.split(r"[\s\u3000\xa0]+", cleaned) if part]
    names: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r"[\u3400-\u9fff]", token) and index + 1 < len(tokens) and re.fullmatch(r"[\u3400-\u9fff]", tokens[index + 1]):
            token += tokens[index + 1]
            index += 1
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", token):
            names.append(token)
        index += 1
    return names


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按强标签与连续姓名段落解析允许角色。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".z-page-inner")
    if region is None:
        raise RuntimeError("未找到领导机构正文.z-page-inner")
    subjects = {
        "discipline": "中国共产党天津市第十二届纪律检查委员会",
        "supervision": "天津市监察委员会",
    }
    allowed = {
        "discipline": {"书记", "副书记", "常务委员会委员"},
        "supervision": {"主任", "副主任"},
    }
    kind = "discipline"
    active_role = ""
    ordered_names: list[str] = []
    duties_by_name: dict[str, list[str]] = {}
    for paragraph in region.find_all("p"):
        if paragraph.find("p") is not None:
            continue
        strong = paragraph.select_one("strong")
        paragraph_text = paragraph.get_text(" ", strip=True)
        names_text = paragraph_text
        if strong is not None:
            label_raw = strong.get_text(" ", strip=True)
            label = compact(label_raw)
            if label == subjects["discipline"]:
                kind, active_role = "discipline", ""
                continue
            if label == subjects["supervision"]:
                kind, active_role = "supervision", ""
                continue
            active_role = label if label in allowed[kind] else ""
            if not active_role:
                continue
            names_text = paragraph_text[len(label_raw):] if paragraph_text.startswith(label_raw) else ""
        elif not active_role:
            continue
        names = extract_names(names_text)
        duty = f"{subjects[kind]}{active_role}"
        for name in names:
            if name not in duties_by_name:
                duties_by_name[name] = []
                ordered_names.append(name)
            if duty not in duties_by_name[name]:
                duties_by_name[name].append(duty)
    if not ordered_names:
        raise RuntimeError("领导机构正文未提取到允许角色记录")
    return [
        {"name": name, "duty": "；".join(duties_by_name[name]), "evidence": "；".join(duties_by_name[name]),
         "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")),
         "selector_summary": ".z-page-inner强标签与连续姓名段落；遇非允许角色停止"}
        for name in ordered_names
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
