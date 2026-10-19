from __future__ import annotations

import sys
import re
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4513",
    "page_type": "纪委监委标题职务名单",
    "structure_group": "sichuan_discipline_supervision_heading_groups_v1",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染（HTTP通道被站点导向浏览器升级页）",
    "force_browser": True,
    "extract_mode": "role_sections",
    "parser": "page_sichuan_discipline_supervision_heading_groups_v1",
    "leader_region_selector": ".font-box.padding_tb10.middle",
    "name_selector": "允许职务h4内a",
    "duty_selector": "h4 > strong.font_20",
    "detail_link_selector": "h4 a[href]",
    "detail_strategy": {"required": False, "mode": "direct_person_link"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "HTTP响应会跳转浏览器升级页，需全局链路降级至Playwright；同页委员名单仅排除，注释中的历史人物不会进入DOM选择器。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按机构标题和允许职务h4原序提取人物并合并同人任职。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".font-box.padding_tb10.middle")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .font-box.padding_tb10.middle")
    allowed = {"书记", "副书记", "常务委员会委员", "主任", "副主任"}
    order: list[str] = []
    duties: dict[str, list[str]] = {}
    details: dict[str, str] = {}
    for section in region.select(":scope > .mg_top40"):
        heading = section.select_one(":scope > h3")
        subject = re.sub(r"\s+", "", heading.get_text(" ", strip=True) if heading else "")
        if not (subject.endswith("纪律检查委员会") or subject.endswith("监察委员会")):
            continue
        for group in section.select(":scope > h4"):
            role_node = group.select_one(":scope > strong.font_20")
            role = re.sub(r"\s+", "", role_node.get_text(" ", strip=True) if role_node else "")
            if role not in allowed:
                continue
            for link in group.select("a"):
                name = re.sub(r"[\s\u00a0\u3000]+", "", link.get_text(" ", strip=True))
                name = re.sub(r"（[^）]*）", "", name)
                if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
                    continue
                if name not in duties:
                    duties[name] = []
                    details[name] = ""
                    order.append(name)
                evidence = f"{subject}{role}"
                if evidence not in duties[name]:
                    duties[name].append(evidence)
                href = str(link.get("href") or "").strip()
                if href and not details[name]:
                    details[name] = urljoin(final_url, href)
    rows = [{"name": name, "duty": "；".join(duties[name]), "evidence": "；".join(duties[name]), "detail_url": details[name], "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".font-box内按h3机构主体和h4>strong允许职务解析a姓名；委员组排除；同人按首次出现合并"} for name in order]
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
