from __future__ import annotations
import re
import sys
import warnings
from pathlib import Path

import requests
from urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4549", "page_type": "省检察院领导简介段落",
    "structure_group": "jiangsu_procuratorate_profile_paragraphs_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_jiangsu_procuratorate_profile_paragraphs_v1",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": ".TRS_Editor p简介开头姓名", "duty_selector": ".TRS_Editor p简介内现任句",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", 
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "站点TLS链不稳定，页面解析器在线复取当前入口并仅在证书校验失败时对同一URL降级；只在正文编辑器内逐段提取现任句。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    current_url = str(page_rule["url"])
    try:
        response = requests.get(current_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    except requests.exceptions.SSLError:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            response = requests.get(
                current_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
                verify=False,
            )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        raise RuntimeError("未找到省检察院领导正文 .TRS_Editor")
    rows: list[dict[str, str]] = []
    for paragraph in region.select("p"):
        text = clean(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u3400-\u9fff·]{2,6})，[男女]，.*?。现任(?P<duty>[^。]+)。?",
            text,
        )
        if match is None:
            continue
        duty = match.group("duty").strip("，,；;。 ")
        if "人民检察院" not in duty:
            raise RuntimeError(f"现任职务无法回指省人民检察院：{match.group('name')}")
        rows.append({"name": match.group("name"), "duty": duty, "evidence": duty, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".TRS_Editor内逐个简介p按DOM原序提取开头姓名和同段现任句"})
    if not rows:
        raise RuntimeError("省检察院领导正文未提取到领导人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
