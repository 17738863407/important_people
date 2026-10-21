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
    "rule_id": "4509",
    "page_type": "纪委监委表格职务名单",
    "structure_group": "shandong_discipline_supervision_table_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "table_role_rows",
    "parser": "page_shandong_discipline_supervision_table_links_v1",
    "leader_region_selector": "含td.ldjg的领导机构表格tbody",
    "name_selector": "允许职务单元格内a",
    "duty_selector": "td.ldjg冒号前职务标题",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "同表含完整纪委委员和监委委员名单；只解析书记、副书记、常委、主任、副主任单元格，javascript占位不作详情链接。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按表格原序解析允许职务行并合并同人纪委、监委任职。"""
    soup = BeautifulSoup(html or "", "html.parser")
    cells = soup.select("td.ldjg")
    if not cells:
        raise RuntimeError("未找到领导机构表格单元格 td.ldjg")
    subject = ""
    order: list[str] = []
    duties: dict[str, list[str]] = {}
    for cell in cells:
        compact = re.sub(r"[\s\u3000]+", "", cell.get_text(" ", strip=True))
        if compact.startswith("中国共产党山东省") and compact.endswith("纪律检查委员会"):
            subject = compact
            continue
        if compact == "山东省监察委员会":
            subject = compact
            continue
        if not subject or "：" not in compact:
            continue
        role_text = compact.split("：", 1)[0]
        base_role = re.sub(r"（[^）]*）", "", role_text)
        if base_role not in {"书记", "副书记", "常委", "主任", "副主任"}:
            continue
        for link in cell.select("a"):
            name = re.sub(r"[\s\u3000]+", "", link.get_text(" ", strip=True))
            name = re.sub(r"（[^）]*）", "", name)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                continue
            if name not in duties:
                duties[name] = []
                order.append(name)
            evidence = f"{subject}{role_text}"
            if evidence not in duties[name]:
                duties[name].append(evidence)
    rows = [{"name": name, "duty": "；".join(duties[name]), "evidence": "；".join(duties[name]), "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": "td.ldjg按机构主体与冒号前允许职务解析a姓名；委员行排除；同人按首次出现合并"} for name in order]
    if not rows:
        raise RuntimeError("领导机构表格未提取到允许职务人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
