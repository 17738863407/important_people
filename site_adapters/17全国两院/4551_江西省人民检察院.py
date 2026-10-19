from __future__ import annotations
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4551", "page_type": "省级检察院正文领导清单",
    "structure_group": "jiangxi_procuratorate_article_paragraphs_v1", "reuse_scope": "single_page",
    "load_mode": "受管代理requests静态HTML", "extract_mode": "custom", "parser": "page_jiangxi_procuratorate_article_paragraphs_v1",
    "leader_region_selector": "td#fontzoom",
    "name_selector": "td#fontzoom直接子p句首姓名", "duty_selector": "姓名后的江西省人民检察院现职",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "公共跳转探测会误把页面“手机端”文字当相对跳转；使用遵从环境代理的requests读取原始HTML并按UTF-8解码；领导正文中的检察委员会委员、专职委员等均按原序保留。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """读取实时正文领导段落，包含检委会委员与专职委员。"""
    session = requests.Session()
    response = session.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.content.decode("utf-8", errors="replace"), "html.parser")
    region = soup.select_one("td#fontzoom")
    if region is None:
        raise RuntimeError("实时页面缺少领导正文td#fontzoom")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = re.sub(r"[\s\u3000\xa0]+", " ", paragraph.get_text(" ", strip=True)).strip()
        match = re.match(r"^([\u3400-\u9fff·]{2,10})\s+(江西省人民检察院.+)$", text)
        if match is None:
            continue
        name, raw_duty = match.groups()
        if name in seen:
            continue
        duty = clean(raw_duty)
        if not duty:
            continue
        seen.add(name)
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "confidence": "high", "parser": str(page_rule.get("parser", "")),
            "selector_summary": "td#fontzoom直接子段落；句首姓名与现职；包含检委会委员类职务",
        })
    if not rows:
        raise RuntimeError("领导正文未提取到人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
