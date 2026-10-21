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
    "rule_id": "4493",
    "page_type": "纪委监委职务分组名单",
    "structure_group": "guangdong_discipline_supervision_role_sections_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "role_sections",
    "parser": "page_guangdong_discipline_supervision_role_sections_v1",
    "leader_region_selector": "#section .article",
    "name_selector": "职务标题后的段落文本",
    "duty_selector": "书记、副书记、常委会委员、主任、副主任标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "同页含完整纪委委员和监委委员名单；只解析书记、副书记、常委会委员、主任、副主任分组并按首次出现顺序合并同人职务。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("#section .article")
    if region is None:
        raise RuntimeError("未找到领导机构正文 #section .article")
    allowed_roles = {"书记", "副书记", "常委会委员", "主任", "副主任"}
    subject = ""
    role = ""
    order: list[str] = []
    duties: dict[str, list[str]] = {}
    for paragraph in region.select("p"):
        text = re.sub(r"[\s\u00a0\u3000]+", " ", paragraph.get_text(" ", strip=True)).strip()
        compact = re.sub(r"\s+", "", text)
        if not compact:
            continue
        if compact.startswith("中国共产党广东省") and compact.endswith("纪律检查委员会"):
            subject, role = compact, ""
            continue
        if compact == "广东省监察委员会":
            subject, role = compact, ""
            continue
        normalized_role = compact.replace(" ", "")
        if normalized_role in allowed_roles:
            role = normalized_role
            continue
        if "委员" in normalized_role or "按姓氏笔画" in normalized_role:
            role = ""
            continue
        if not subject or role not in allowed_roles:
            continue
        for token in re.split(r"\s+", re.sub(r"[（(][男女][）)]", "", text)):
            name = token.strip("，,、；; ")
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                continue
            if name not in duties:
                duties[name] = []
                order.append(name)
            evidence = f"{subject}{role}"
            if evidence not in duties[name]:
                duties[name].append(evidence)
    rows = [
        {"name": name, "duty": "；".join(duties[name]), "evidence": "；".join(duties[name]), "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "#section .article按机构标题与允许职务分组解析；排除委员名单；同人按首次出现合并"}
        for name in order
    ]
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
