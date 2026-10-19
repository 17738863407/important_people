from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2892",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_health_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "haikou_health_leader_cards_v1",
    "leader_region_selector": ".gkpd-l-nr a[href]:has(.ldmc):has(.ldzw)",
    "name_selector": ".ldmc",
    "duty_selector": ".ldzw",
    "detail_link_selector": "a[href]",
    "detail_strategy": {"required": False, "mode": "list_link"},
    "risk_flag": "限定机构介绍页领导信息容器，排除新闻人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理卡片文本中的排版空白与外层方括号。"""
    return re.sub(r"\s+", " ", value or "").strip().strip("[]【】 ")


def valid_detail_url(href: str, final_url: str) -> str:
    """仅保留当前人物卡片的站内独立详情页。"""
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return ""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc or detail_url.rstrip("/") == final_url.rstrip("/"):
        return ""
    if not re.search(r"/ldxx/\d{6}/t\d+\.shtml(?:$|[?#])", detail_url):
        return ""
    return detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按页面DOM顺序解析卫健委领导卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    for link in soup.select(".gkpd-l-nr a[href]:has(.ldmc):has(.ldzw)"):
        name_node = link.select_one(".ldmc")
        duty_node = link.select_one(".ldzw")
        name = clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": valid_detail_url(link.get("href", ""), final_url),
                "selector_summary": ".gkpd-l-nr人物链接内.ldmc姓名与.ldzw职务",
            }
        )
    if not records:
        raise ValueError("未在卫健委领导信息容器中解析到有效人物")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
