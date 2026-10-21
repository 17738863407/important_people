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
    "rule_id": "4519", "page_type": "纪委监委领导机构正文页",
    "structure_group": "chongqing_discipline_supervision_paragraphs_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML（同站HTTP入口）", "extract_mode": "custom", "parser": "page_chongqing_discipline_supervision_paragraphs_v1",
    "leader_region_selector": ".container-news-content .ck-content", "name_selector": "目标职务p中strong后的文本",
    "duty_selector": "p > span > strong", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "HTTPS入口受WAF阻断，使用同站HTTP入口；只保留书记/副书记/常委及主任/副主任，排除委员。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    url = str(page_rule["url"])
    fetch_url = re.sub(r"^https://", "http://", url)
    response = requests.get(fetch_url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml", "Referer": "https://jjc.cq.gov.cn/"})
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    region = soup.select_one(".container-news-content .ck-content")
    if region is None:
        raise RuntimeError("未找到领导机构正文 .container-news-content .ck-content")
    subject = ""
    people: OrderedDict[str, list[str]] = OrderedDict()
    role_map = {"书记": "书记", "副书记": "副书记", "常务委员会委员": "常委", "主任": "主任", "副主任": "副主任"}
    for paragraph in region.find_all("p", recursive=False):
        strong = paragraph.find("strong")
        label = compact(strong.get_text(" ", strip=True)).rstrip("：:") if strong else ""
        if "纪律检查委员会" in label or label == "重庆市监察委员会":
            subject = label
            continue
        role = role_map.get(label)
        if not role or not subject or strong is None:
            continue
        strong.extract()
        raw = re.sub(r"[（(][^）)]*[）)]", "", paragraph.get_text(" ", strip=True))
        duty = subject + role
        for token in re.split(r"[、，,;；\s\u3000\xa0]+", raw):
            name = compact(token)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
                continue
            duties = people.setdefault(name, [])
            if duty not in duties:
                duties.append(duty)
    rows = []
    for name, duties in people.items():
        evidence = "；".join(duties)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": ".container-news-content .ck-content直属p；strong职务；排除委员"})
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
