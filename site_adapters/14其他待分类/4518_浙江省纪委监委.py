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
    "rule_id": "4518",
    "page_type": "纪委监委同页强结构领导机构",
    "structure_group": "zhejiang_discipline_supervision_combined_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_zhejiang_discipline_supervision_combined_v1",
    "leader_region_selector": ".artCon",
    "name_selector": ".artCon p允许角色标签后的姓名",
    "duty_selector": ".artCon p > strong",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "纪委与监委同页；姓名中有排版空格；仅保留纪委书记、副书记、常务委员会委员及监委主任、副主任，排除两个委员名单。",
}


def compact(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value or "")


def extract_names(value: str) -> list[str]:
    cleaned = re.sub(r"（[^）]*）|\([^)]*\)", "", value or "")
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
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".artCon")
    if region is None:
        raise RuntimeError("未找到领导机构正文.artCon")
    subjects = {"discipline": "中国共产党浙江省第十五届纪律检查委员会", "supervision": "浙江省监察委员会"}
    allowed = {"discipline": {"书记", "副书记", "常务委员会委员"}, "supervision": {"主任", "副主任"}}
    kind = "discipline"
    ordered_names: list[str] = []
    duties_by_name: dict[str, list[str]] = {}
    for paragraph in region.select("p"):
        strong = paragraph.select_one("strong")
        if strong is None:
            continue
        label_raw = strong.get_text(" ", strip=True)
        label = compact(label_raw)
        if label == subjects["discipline"]:
            kind = "discipline"
            continue
        if label == subjects["supervision"]:
            kind = "supervision"
            continue
        if label not in allowed[kind]:
            continue
        paragraph_text = paragraph.get_text(" ", strip=True)
        names_text = paragraph_text[len(label_raw):] if paragraph_text.startswith(label_raw) else paragraph_text
        names = extract_names(names_text)
        if not names:
            raise RuntimeError(f"角色{label}未解析到姓名")
        duty = f"{subjects[kind]}{label}"
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
         "selector_summary": ".artCon段落strong角色标签及标签后姓名；按页面顺序合并"}
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
