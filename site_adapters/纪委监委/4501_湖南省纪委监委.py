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
    "rule_id": "4501",
    "page_type": "纪委监委段落职务名单",
    "structure_group": "hunan_discipline_supervision_paragraph_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "role_sections",
    "parser": "page_hunan_discipline_supervision_paragraph_groups_v1",
    "leader_region_selector": ".content-detail-context",
    "name_selector": "允许职务段落中strong标题后的文本",
    "duty_selector": "strong中的书记、副书记、常务委员会委员、主任、副主任",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "同页含55名纪委委员及监委委员名单；只解析允许职务段落，按首次出现顺序合并同人纪委、监委职务。",
}

def split_names(value: str) -> list[str]:
    """按网页排版空白拆名，并合并两个连续单字组成的双字姓名。"""
    value = re.sub(r"[（(][^）)]*[）)]", "", value)
    tokens = [item for item in re.split(r"\s+", value) if item]
    result: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index].strip("，,、；; ")
        if len(token) == 1 and index + 1 < len(tokens) and len(tokens[index + 1]) == 1:
            token += tokens[index + 1]
            index += 2
        else:
            index += 1
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", token):
            result.append(token)
    return result


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".content-detail-context")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .content-detail-context")
    allowed = {"书记", "副书记", "常务委员会委员", "主任", "副主任"}
    subject = ""
    order: list[str] = []
    duties: dict[str, list[str]] = {}
    for paragraph in region.select("p"):
        full_text = paragraph.get_text(" ", strip=True)
        compact = re.sub(r"\s+", "", full_text)
        if compact.startswith("中国共产党湖南省") and compact.endswith("纪律检查委员会"):
            subject = compact
            continue
        if compact == "湖南省监察委员会":
            subject = compact
            continue
        strong_text = "".join(node.get_text(" ", strip=True) for node in paragraph.select("strong"))
        role_text = re.sub(r"\s+", "", strong_text)
        role = next((item for item in allowed if role_text == item), "")
        if not subject or not role:
            continue
        names_text = full_text
        if strong_text:
            names_text = names_text.replace(strong_text, "", 1)
        for name in split_names(names_text):
            if name not in duties:
                duties[name] = []
                order.append(name)
            evidence = f"{subject}{role}"
            if evidence not in duties[name]:
                duties[name].append(evidence)
    rows = [{"name": name, "duty": "；".join(duties[name]), "evidence": "；".join(duties[name]), "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".content-detail-context按主体段落与strong允许职务解析；委员段落排除；同人按首次出现合并"} for name in order]
    if not rows:
        raise RuntimeError("领导机构正文未提取到书记、副书记、常委或监委主任、副主任")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
