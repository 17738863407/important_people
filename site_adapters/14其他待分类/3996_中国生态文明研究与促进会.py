from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
import urllib3
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3996", "page_type": "协会会领导正文页", "structure_group": "cecrpa_leaders_text", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "custom", "collector": "raw_http", "parser": "custom_cecrpa_leaders_text_v1", "inline_parser_handles_fetch": True, "inline_fetch_collector": "raw_http",
    "leader_region_selector": ".article, .content", "name_selector": "正文会长姓名及副会长名单", "duty_selector": "现任句与副会长标题", "detail_link_selector": "",
    "content_scope": {"start_anchor": "会领导", "end_anchor": "联系我们", "include_selectors": [".article", ".content"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none"}, "risk_flag": "正文包含张波的历史履历；仅现任句可作会长依据，副会长以明确标题对应名单。",
    "confidence": "high", "profile_reusable": False, "profile_judgement": "已核验标题、会长现任句和副会长姓名名单均在同一当前正文区域。", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": ".article, .content"}, "api": {"enabled": False, "reason": "当前HTML正文完整呈现会领导信息"}, "migration": {"verified_status": "verified"}},
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def fetch_authoritative_html(page_rule: dict[str, object]) -> str:
    """使用直连原始响应，规避该站证书主机名错误及浏览器误跳转页。"""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.trust_env = False
    response = session.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
    response.raise_for_status()
    return response.content.decode("utf-8", errors="replace")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """依据正文顺序提取会长现任句及“副会长”标题后名单。"""
    html = fetch_authoritative_html(page_rule)
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".ej_ld")
    if root is None:
        return []
    leader_card = root.select_one(".ej_ld_h1")
    leader_text = clean_text(leader_card.get_text(" ", strip=True)) if leader_card else ""
    leader_match = re.search(r"([\u4e00-\u9fff]{2,4})\s*会长.*?现任\s*(中国生态文明研究与促进会会长)", leader_text)
    if leader_match is None:
        return []
    rows = [{"name": leader_match.group(1), "duty": leader_match.group(2), "detail_url": "", "evidence": leader_match.group(2), "parser": str(page_rule.get("parser", "")), "selector_summary": "正文会长段落现任句"}]
    for name_node in root.select(".ld_list .ld_name"):
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or any(row["name"] == name for row in rows):
            continue
        rows.append({"name": name, "duty": "副会长", "detail_url": "", "evidence": "副会长", "parser": str(page_rule.get("parser", "")), "selector_summary": "正文“副会长”标题后的姓名名单"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
