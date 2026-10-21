from __future__ import annotations
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, Tag

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4497",
    "page_type": "纪委监委职务分组名单",
    "structure_group": "hebei_discipline_supervision_ul_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "role_sections",
    "parser": "page_hebei_discipline_supervision_ul_groups_v1",
    "leader_region_selector": ".min_content",
    "name_selector": "ul.cx > li:not(.bold)",
    "duty_selector": "ul.cx > li.bold可见职务标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "同页含完整委员名单且监委主任标题有隐藏重复节点；只读取可见允许职务分组，排除委员分组。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".min_content")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .min_content")
    allowed_roles = {"书记", "副书记", "常务委员会委员", "主任", "副主任"}
    subject = ""
    order: list[str] = []
    duties: dict[str, list[str]] = {}
    for child in region.find_all(["p", "ul"], recursive=False):
        if child.name == "p":
            text = re.sub(r"\s+", "", child.get_text(" ", strip=True))
            if text.startswith("中国共产党河北省") and text.endswith("纪律检查委员会"):
                subject = text
            elif text == "河北省监察委员会":
                subject = text
            continue
        if "cx" not in child.get("class", []) or not subject:
            continue
        role_node = next(
            (
                node for node in child.select(":scope > li.bold")
                if "display:none" not in str(node.get("style", "")).replace(" ", "").lower()
            ),
            None,
        )
        role = re.sub(r"\s+", "", role_node.get_text(" ", strip=True) if role_node else "")
        if role not in allowed_roles:
            continue
        for node in child.select(":scope > li:not(.bold)"):
            if not isinstance(node, Tag):
                continue
            name = re.sub(r"[\s\u00a0]+", "", node.get_text(" ", strip=True))
            name = re.sub(r"[（(][^）)]*[）)]", "", name)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                continue
            if name not in duties:
                duties[name] = []
                order.append(name)
            evidence = f"{subject}{role}"
            if evidence not in duties[name]:
                duties[name].append(evidence)
    rows = [{"name": name, "duty": "；".join(duties[name]), "evidence": "；".join(duties[name]), "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".min_content直属p确定机构主体、ul.cx可见bold确定允许职务；委员分组排除；同人按首次出现合并"} for name in order]
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
