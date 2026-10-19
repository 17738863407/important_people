from __future__ import annotations
import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4547", "page_type": "领导分组详情页",
    "structure_group": "jilin_procuratorate_leader_details_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_jilin_procuratorate_v1",
    "leader_region_selector": "a[href*='/yld/']",
    "name_selector": "a[href*='/yld/']", "duty_selector": "#fontzoom.contentbd p",
    "detail_link_selector": "a[href*='/yld/']", "detail_strategy": {"required": True, "mode": "detail_page"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析院领导列表及其详情页；检察委员会委员、专职委员等委员类职务均按网页原文完整保留。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers=headers)
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    candidates: list[tuple[str, str]] = []
    for link in soup.select("a[href]"):
        href = str(link.get("href") or "")
        name = clean(link.get_text(" ", strip=True))
        if not re.search(r"/yld/\d{6}/t\d+_\d+\.shtml$", href) or not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        candidates.append((name, urljoin(response.url, href)))

    rows: list[dict[str, str]] = []
    for name, detail_url in candidates:
        detail = requests.get(detail_url, timeout=30, verify=False, headers=headers)
        detail.raise_for_status()
        detail.encoding = "utf-8"
        detail_soup = BeautifulSoup(detail.text, "html.parser")
        paragraphs = [
            clean(node.get_text(" ", strip=True))
            for node in detail_soup.select("#fontzoom.contentbd p")
        ]
        name_index = next((index for index, text in enumerate(paragraphs) if text == name), -1)
        duty = next((text for text in paragraphs[name_index + 1:] if text), "") if name_index >= 0 else ""
        duty = duty.strip("，。")
        if not duty:
            raise RuntimeError(f"人物详情页缺少可验证的领导职务：{detail_url}")
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": detail.url,
            "parser": str(page_rule["parser"]),
            "selector_summary": "院领导列表 + #fontzoom.contentbd详情首项职务",
        })
    if not rows:
        raise RuntimeError("院领导分组未提取到人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
