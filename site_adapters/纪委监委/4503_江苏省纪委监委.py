from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4503", "page_type": "纪委监委领导机构分组页",
    "structure_group": "jiangsu_discipline_supervision_groups_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_jiangsu_discipline_supervision_groups_v1",
    "leader_region_selector": "包含纪委、监委标题及书记至委员分组的正文容器",
    "name_selector": "目标职务标题后的姓名文本或链接",
    "duty_selector": "书记、副书记、常务委员会委员、主任、副主任",
    "detail_link_selector": "目标职务分组内a[href]", "detail_strategy": {"required": False, "mode": "person_anchor"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "medium", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；排除委员名单；站点阻断时明确失败。",
}


def clean(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0：:]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    response = requests.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml"})
    if response.status_code != 200:
        raise RuntimeError(f"江苏纪检监察站点防火墙或页面策略阻断（HTTP {response.status_code}）")
    response.encoding = "utf-8"
    final_url = response.url
    soup = BeautifulSoup(response.text, "html.parser")
    regions = [node for node in soup.find_all(["div", "article", "main"]) if "纪律检查委员会" in node.get_text(" ", strip=True) and "监察委员会" in node.get_text(" ", strip=True)]
    if not regions:
        raise RuntimeError("未找到同时包含纪委、监委领导分组的正文容器")
    region = min(regions, key=lambda node: len(node.get_text(" ", strip=True)))
    subject = ""
    role = ""
    people: OrderedDict[str, dict[str, object]] = OrderedDict()
    role_map = {"书记": "书记", "副书记": "副书记", "常务委员会委员": "常委", "主任": "主任", "副主任": "副主任"}
    for element in region.find_all(["h1", "h2", "h3", "h4", "p", "li", "div"]):
        if element.find(["h1", "h2", "h3", "h4", "p", "li", "div"], recursive=False):
            continue
        text = element.get_text(" ", strip=True)
        label = clean(text)
        if "纪律检查委员会" in label and len(label) < 40:
            subject = re.sub(r"\s+", "", text); role = ""; continue
        if "监察委员会" in label and "纪律检查委员会" not in label and len(label) < 30:
            subject = re.sub(r"\s+", "", text); role = ""; continue
        if label.startswith("委员") and label != "常务委员会委员":
            role = ""; continue
        matched = role_map.get(label)
        if matched:
            role = matched; continue
        if not subject or not role:
            continue
        for token in re.split(r"[、，,;；\s\u2002\u3000]+", text):
            name = clean(re.sub(r"[（(].*?[）)]", "", token))
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                continue
            duty = subject + role
            item = people.setdefault(name, {"duties": [], "detail_url": ""})
            duties = item["duties"]
            if isinstance(duties, list) and duty not in duties:
                duties.append(duty)
            anchor = element.find("a", string=lambda value: bool(value and clean(value) == name))
            if anchor and anchor.get("href"):
                item["detail_url"] = urljoin(final_url, str(anchor["href"]))
    rows = []
    for name, item in people.items():
        duties = item["duties"]
        evidence = "；".join(duties) if isinstance(duties, list) else ""
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": str(item["detail_url"]), "parser": str(page_rule.get("parser", "")), "selector_summary": "纪委监委正文叶节点按职务分组；排除委员"})
    if not rows:
        raise RuntimeError("未提取到目标纪委监委领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
