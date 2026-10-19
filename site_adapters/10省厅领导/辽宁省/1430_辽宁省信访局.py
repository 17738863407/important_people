from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1430",
    "domain": "www.lnxf.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "leader_cards_name_role_detail_current_verify_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail_verify",
    "collector": "static_http",
    "parser": "page_inline_leader_cards_name_role_detail_current_verify_v1",
    "leader_region_selector": ".xxgk_n_l_ts",
    "name_selector": ".xxgk_n_l_ts_lib",
    "duty_selector": ".xxgk_n_l_ts_lia",
    "detail_link_selector": "a[href]",
    "detail_person_selector": ".about_right_text_rs",
    "detail_name_selector": ".about_right_text_rs_top",
    "detail_intro_selector": ".about_right_text_rs_text",
    "detail_strategy": {"required": True, "mode": "card_role_detail_current_verify"},
    "risk_flag": "公共online误跟随站内搜索模板location跳转；入口须保留原始响应；详情须按本人容器核验",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩卡片和详情中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: object) -> str:
    """移除姓名中的排版空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def validate_detail(
    detail_url: str,
    expected_name: str,
    expected_duty: str,
    page_rule: dict[str, object],
    attempt_offset: int,
) -> bool:
    """在线确认详情存在包含本人姓名和卡片职务的现任简介。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    soup = BeautifulSoup(result.html, "html.parser")
    person = soup.select_one(str(page_rule.get("detail_person_selector", "")))
    if person is None:
        return False
    name_node = person.select_one(str(page_rule.get("detail_name_selector", "")))
    intro_node = person.select_one(str(page_rule.get("detail_intro_selector", "")))
    if name_node is None or intro_node is None:
        return False
    if clean_name(name_node.get_text(" ", strip=True)) != expected_name:
        return False
    text = clean_text(intro_node.get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    return bool(match and expected_duty in match.group(0))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片顺序提取姓名职务，并在线核验详情归属。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for source_order, link in enumerate(region.select("a[href]"), start=1):
        name_node = link.select_one(str(page_rule.get("name_selector", "")))
        duty_node = link.select_one(str(page_rule.get("duty_selector", "")))
        if name_node is None or duty_node is None:
            continue
        name = clean_name(name_node.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        href = str(link.get("href", ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or not href or name in seen:
            continue
        detail_url = urljoin(final_url or source_url, href)
        try:
            if not validate_detail(detail_url, name, duty, page_rule, source_order):
                continue
        except Exception:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.xxgk_n_l_ts；"
                    "name=.xxgk_n_l_ts_lib；duty=.xxgk_n_l_ts_lia；"
                    "detail=.about_right_text_rs same-name 现任 sentence verification"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
