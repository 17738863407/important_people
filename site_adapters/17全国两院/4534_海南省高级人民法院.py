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
    "rule_id": "4534",
    "page_type": "省级法院检察院领导页面待核验",
    "structure_group": "hainan_high_court_pending_v1",
    "reuse_scope": "single_page",
    "load_mode": "在线页面待核验",
    "extract_mode": "custom",
    "parser": "page_hainan_high_court_pending_v1",
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
    "risk_flag": "当前入口为审判委员会组成等领导信息区域；委员、专职委员与其他院级领导均保留，无实时证据时明确失败。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """实际重试权威入口；无可验证页面时拒绝猜测名单。"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36", "Referer": "https://www.hicourt.gov.cn/"}
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers=headers)
    response.raise_for_status(); response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser"); rows = []
    for link in soup.select("a[href*='/article/detail/']"):
        text = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
        match = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,10})", text)
        if match is None: continue
        duty, name = match.groups()
        if "海南省高级人民法院" not in duty or not re.search(r"党组|院长|副院长|政治部主任|审判委员会委员|专职委员", duty): continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(response.url, str(link.get("href") or "")), "parser": str(page_rule["parser"]), "selector_summary": "审判委员会组成等领导信息区域中的院级领导及委员链接"})
    if not rows: raise RuntimeError("未提取到领导信息区域人物")
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
