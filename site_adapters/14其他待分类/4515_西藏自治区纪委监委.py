from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4515", "page_type": "纪委监委领导机构正文页",
    "structure_group": "tibet_discipline_supervision_paragraphs_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_tibet_discipline_supervision_paragraphs_v1",
    "leader_region_selector": ".content", "name_selector": "目标职务p冒号后文本",
    "duty_selector": "目标职务p冒号前文本", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；委员段及后续名单排除。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def names_from(value: str) -> list[str]:
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", value)
    return [name for token in re.split(r"[、，,;；]+", cleaned) if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", (name := compact(token)))]


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    response = requests.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = "utf-8"
    final_url = response.url
    soup = BeautifulSoup(response.text, "html.parser")
    region = soup.select_one(".content")
    if region is None or "纪律检查委员会" not in region.get_text(" ", strip=True):
        raise RuntimeError("未找到领导机构正文 .content")
    subject = ""
    people: OrderedDict[str, list[str]] = OrderedDict()
    for paragraph in region.find_all("p", recursive=False):
        text = paragraph.get_text(" ", strip=True)
        label = compact(text)
        if "纪律检查委员会" in label and "：" not in label and ":" not in label:
            subject = label
            continue
        if label == "西藏自治区监察委员会":
            subject = label
            continue
        if not subject:
            continue
        match = re.match(r"^(书记|副书记|常务委员会委员\d*名|主任|副主任)[：:](.*)$", label)
        if not match:
            continue
        role_label, raw_names = match.groups()
        role = "常委" if role_label.startswith("常务委员会委员") else role_label
        duty = subject + role
        for name in names_from(raw_names):
            duties = people.setdefault(name, [])
            if duty not in duties:
                duties.append(duty)
    rows = []
    for name, duties in people.items():
        evidence = "；".join(duties)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": ".content直属p按冒号职务分组；排除委员段"})
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
