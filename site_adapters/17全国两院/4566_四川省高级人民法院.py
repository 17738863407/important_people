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
    "rule_id": "4566",
    "page_type": "省级法院院长介绍列表转详情",
    "structure_group": "sichuan_high_court_president_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "受管代理requests静态HTML",
    "extract_mode": "list_to_detail",
    "parser": "page_sichuan_high_court_president_detail_v1",
    "leader_region_selector": "#main .list_br a[href*='/article/detail/']",
    "name_selector": "详情div.text句首姓名",
    "duty_selector": "详情div.text现任句",
    "detail_link_selector": "a[href*='/article/detail/']",
    "detail_strategy": {"required": True, "mode": "person_detail"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "当前权威栏目仅提供1篇院长介绍；入口分页脚本含[page]占位，使用遵从环境代理的requests读取原始入口，并带Referer抓取详情；现任句中的委员类职务同样完整保留。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """读取当前院长介绍详情中的姓名和现任职务。"""
    url = str(page_rule.get("url") or "").strip()
    if not url:
        raise RuntimeError("规则主表领导链接为空，无法在线核验领导页面")
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}
    response = session.get(url, timeout=30, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.select("#main .list_br a[href*='/article/detail/']")
    if len(links) != 1:
        raise RuntimeError(f"院长介绍栏目人物详情链接数量异常：{len(links)}")
    detail_url = urljoin(url, str(links[0].get("href") or ""))
    detail_response = session.get(detail_url, timeout=30, headers={**headers, "Referer": url})
    detail_response.raise_for_status()
    detail_soup = BeautifulSoup(detail_response.text, "html.parser")
    text_node = detail_soup.select_one("div.text")
    if text_node is None:
        raise RuntimeError("院长详情缺少div.text正文")
    text = re.sub(r"\s+", "", text_node.get_text(" ", strip=True))
    name_match = re.match(r"([\u3400-\u9fff·]{2,10})，", text)
    duty_match = re.search(r"现任(.+?)(?:。|$)", text)
    if name_match is None or duty_match is None:
        raise RuntimeError("院长详情未识别到句首姓名或现任职务")
    duty = duty_match.group(1).strip("，,；;。 ")
    if not re.search(r"党组|院长", duty):
        raise RuntimeError("院长详情现任句无可验证院级领导职务")
    return [{
        "name": name_match.group(1), "duty": duty, "evidence": duty, "detail_url": detail_url,
        "confidence": "high", "parser": str(page_rule.get("parser", "")),
        "selector_summary": "院长介绍列表唯一详情；div.text句首姓名与现任句",
    }]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
