from __future__ import annotations

import sys
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4568",
    "page_type": "审判委员会组成领导列表",
    "structure_group": "tianjin_high_court_committee_leaders_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_tianjin_high_court_committee_leaders_v1",
    "leader_region_selector": "div#list a[title][href]",
    "name_selector": "a[title]标题末尾姓名",
    "duty_selector": "a[title]标题中的完整职务",
    "detail_link_selector": "a[title][href]",
    "detail_strategy": {"required": False, "mode": "same_list"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "页面分组为审判委员会组成；按列表原序保留全部成员及完整委员职务。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从实时审判委员会组成列表的完整 title 中提取全部成员。"""
    url = str(page_rule.get("url") or "").strip()
    if not url:
        raise RuntimeError("规则主表领导链接为空，无法在线核验领导页面")
    response = requests.get(
        url, timeout=30, verify=False,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select("div#list a[title][href]"):
        title = re.sub(r"[\s\u3000\xa0]+", "", str(link.get("title") or ""))
        match = re.search(r"(?:委员|大法官|高级法官|副院长|院长)([\u3400-\u9fff·]{2,4})$", title)
        if match is None:
            continue
        name = match.group(1)
        duty = title[:-len(name)]
        duty_parts = [part for part in re.split(r"[、；;]", duty) if part]
        duty = "、".join(duty_parts)
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": urljoin(response.url, str(link.get("href") or "")),
            "parser": str(page_rule["parser"]),
            "selector_summary": "审判委员会组成列表完整title中的全部成员及职务",
        })
    if not rows:
        raise RuntimeError("审判委员会组成列表未提取到有效成员")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
