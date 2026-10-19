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
    "rule_id": "4502",
    "page_type": "纪委监委同页强结构领导机构",
    "structure_group": "jilin_discipline_supervision_combined_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_jilin_discipline_supervision_combined_v1",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": ".TRS_Editor p允许角色标签后的正文姓名",
    "duty_selector": ".TRS_Editor p > strong",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "纪委与监委同页；仅保留纪委书记、副书记、常务委员会委员及监委主任、副主任，显式排除两个委员段落；多人共用机构页不写详情页。",
}


def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def extract_names(value: str) -> list[str]:
    """按正文顺序解析姓名；合并网页在双字姓名中插入的排版空格。"""
    cleaned = re.sub(r"（[^）]*）|\([^)]*\)", "", value or "")
    tokens = [token for token in re.split(r"[\s\u3000\xa0]+", cleaned) if token]
    names: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index].strip("，,、；;：:")
        if re.fullmatch(r"[\u3400-\u9fff]", token) and index + 1 < len(tokens):
            following = tokens[index + 1].strip("，,、；;：:")
            if re.fullmatch(r"[\u3400-\u9fff]", following):
                token += following
                index += 1
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", token):
            names.append(token)
        index += 1
    return names


def strip_leading_label(value: str, label: str) -> str:
    """从段落开头逐字移除可能被空格或嵌套标签拆开的角色名。"""
    position = 0
    for expected in label:
        while position < len(value) and value[position].isspace():
            position += 1
        if position >= len(value) or value[position] != expected:
            return value
        position += 1
    return value[position:]


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析纪委、监委允许角色，并按页面首次出现顺序合并同人职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .TRS_Editor")
    subjects = {
        "discipline": "中国共产党吉林省第十二届纪律检查委员会",
        "supervision": "吉林省监察委员会",
    }
    allowed = {
        "discipline": {"书记": "书记", "副书记": "副书记", "常务委员会委员": "常务委员会委员"},
        "supervision": {"主任": "主任", "副主任": "副主任"},
    }
    kind = "discipline"
    ordered_names: list[str] = []
    duties_by_name: dict[str, list[str]] = {}
    for paragraph in region.select("p"):
        strong = paragraph.select_one("strong")
        if strong is None:
            continue
        label_raw = strong.get_text(" ", strip=True)
        label = compact(label_raw)
        paragraph_text = paragraph.get_text(" ", strip=True)
        if label == subjects["discipline"]:
            kind = "discipline"
            continue
        if label == subjects["supervision"]:
            kind = "supervision"
            continue
        role = allowed[kind].get(label)
        if role is None:
            compact_paragraph = compact(paragraph_text)
            for candidate in sorted(allowed[kind], key=len, reverse=True):
                if compact_paragraph.startswith(candidate):
                    label = candidate
                    role = allowed[kind][candidate]
                    break
        if role is None:
            continue
        names_text = strip_leading_label(paragraph_text, label)
        names = extract_names(names_text)
        if not names:
            raise RuntimeError(f"角色{label}未解析到姓名")
        duty = f"{subjects[kind]}{role}"
        for name in names:
            if name not in duties_by_name:
                duties_by_name[name] = []
                ordered_names.append(name)
            if duty not in duties_by_name[name]:
                duties_by_name[name].append(duty)
    if not ordered_names:
        raise RuntimeError("领导机构正文未提取到允许角色记录")
    return [
        {
            "name": name,
            "duty": "；".join(duties_by_name[name]),
            "evidence": "；".join(duties_by_name[name]),
            "detail_url": "",
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": ".TRS_Editor段落strong角色标签及标签后姓名；按页面顺序合并",
        }
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
