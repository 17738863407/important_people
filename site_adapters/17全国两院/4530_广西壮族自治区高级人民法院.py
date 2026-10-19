from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4530",
    "page_type": "省级法院检察院领导页面待核验",
    "structure_group": "guangxi_high_court_pending_v1",
    "reuse_scope": "single_page",
    "load_mode": "在线页面待核验",
    "extract_mode": "custom",
    "parser": "page_guangxi_high_court_pending_v1",
    "leader_region_selector": "未取得可验证实时DOM，不猜测选择器",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "当前入口仅展示院长简介；若领导区域出现委员或专职委员则一并保留，无实时证据时明确失败。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36", "Referer": "https://gxfy.gxcourt.gov.cn/"}
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers=headers)
    response.raise_for_status(); response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.select_one(".main .content .tit_br")
    if title is None or "院长简介" not in title.get_text(" ", strip=True): raise RuntimeError("页面未确认院长简介分组")
    rows = []
    for card in soup.select(".main .content .fyjs"):
        link = card.select_one(".fyjs_txt h2 a[href]")
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True) if link else "")
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            rows.append({"name": name, "duty": "院长", "evidence": "院长", "detail_url": urljoin(response.url, str(link.get("href") or "")), "parser": str(page_rule["parser"]), "selector_summary": "院长简介.fyjs卡片"})
    if not rows: raise RuntimeError("院长简介卡片未提取到人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
