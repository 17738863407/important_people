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
    "rule_id": "4539", "page_type": "领导卡片页",
    "structure_group": "henan_procuratorate_leader_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_henan_procuratorate_v1",
    "leader_region_selector": "table.sk20.xk20",
    "name_selector": "a.r16c[href]", "duty_selector": "a.b14c[href]",
    "detail_link_selector": "a.r16c[href]", "detail_strategy": {"required": False, "mode": "same_card"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析领导卡片区域；审判委员会委员、检察委员会委员、专职委员等委员类人物均按网页原序保留。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status(); response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser"); rows = []
    for card in soup.select("table.sk20.xk20"):
        name_link = card.select_one("a.r16c[href]"); duties = card.select("a.b14c[href]")
        name = clean(name_link.get_text(" ", strip=True) if name_link else "")
        duty = clean(duties[-1].get_text(" ", strip=True) if duties else "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not duty: continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(response.url, str(name_link.get("href") or "")), "parser": str(page_rule["parser"]), "selector_summary": "table.sk20.xk20领导卡片"})
    if not rows: raise RuntimeError("领导卡片未提取到人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
