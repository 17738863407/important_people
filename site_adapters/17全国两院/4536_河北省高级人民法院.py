from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\\s\\u3000\\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4536", "page_type": "省级法院人物列表转详情页",
    "structure_group": "hebei_high_court_list_detail_v1", "reuse_scope": "single_page",
    "load_mode": "受管代理requests静态HTML", "extract_mode": "list_to_detail", "parser": "page_hebei_high_court_list_detail_v1",
    "leader_region_selector": "#main .list_br a[href*='/article/detail/']",
    "name_selector": "列表人物链接文本", "duty_selector": "详情页div.text中的现任句",
    "detail_link_selector": "a[href*='/article/detail/']", "detail_strategy": {"required": True, "mode": "person_detail"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "requests",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "入口含分页脚本模板，公共跳转探测会误跟随[page]占位；使用遵从环境代理的requests读取原始列表并以入口为Referer抓取人物详情；领导列表中的审判委员会委员、专职委员均保留。",
}


def filter_duty(value: str) -> str:
    parts = [part.strip() for part in re.split(r"[、；;]", clean(value)) if part.strip()]
    return "、".join(parts)

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从实时领导列表逐页读取人物详情中的现任职务。"""
    entry_url = str(page_rule["url"])
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    response = session.get(entry_url, timeout=30, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select("#main .list_br a[href*='/article/detail/']"):
        name = clean(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        detail_url = urljoin(entry_url, str(link.get("href") or ""))
        detail_response = session.get(detail_url, timeout=30, headers={**headers, "Referer": entry_url})
        detail_response.raise_for_status()
        detail_soup = BeautifulSoup(detail_response.text, "html.parser")
        text_node = detail_soup.select_one("div.text")
        if text_node is None:
            raise RuntimeError(f"人物详情缺少div.text：{detail_url}")
        detail_text = re.sub(r"\s+", "", text_node.get_text(" ", strip=True))
        duty_match = re.search(r"现任(.+?)(?:。|$)", detail_text)
        if duty_match is None:
            raise RuntimeError(f"人物详情缺少现任职务句：{detail_url}")
        duty = filter_duty(duty_match.group(1))
        if not duty or not re.search(r"党组|院长|执行局局长|政治部主任|纪检监察组组长|委员", duty):
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": detail_url,
            "confidence": "high", "parser": str(page_rule.get("parser", "")),
            "selector_summary": "#main领导列表人物链接；详情div.text现任句；完整保留委员类职务",
        })
    if not rows:
        raise RuntimeError("实时领导列表及详情页未提取到合规领导")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
