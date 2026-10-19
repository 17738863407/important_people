from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1814",
    "page_type": "现任领导名单及详情入口页",
    "structure_group": "yunnan_ethnic_leader_window_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_yunnan_ethnic_leader_window_cards_v1",
    "leader_region_selector": "div.news_item.ldzc",
    "name_selector": "ul.ldzc_ul li a b",
    "duty_selector": "ul.ldzc_ul li a span.zzz",
    "detail_link_selector": "ul.ldzc_ul li a[href]",
    "content_scope": {
        "start_anchor": "领导之窗",
        "end_anchor": "内设机构",
        "include_selectors": ["div.news_item.ldzc ul.ldzc_ul li"],
        "exclude_selectors": ["网站导航", "友情链接", "页脚"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_links_only",
        "detail_collector_type": "static_http",
        "detail_link_selector": "ul.ldzc_ul li a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "权威业务入口的旧域名当前SSL协议异常；技术解析仅依赖领导之窗卡片，不在脚本复制替代业务网址",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.news_item.ldzc",
            "name_selector": "ul.ldzc_ul li a b",
            "duty_selector": "ul.ldzc_ul li a span.zzz",
            "detail_link_selector": "ul.ldzc_ul li a[href]",
            "content_scope": {
                "start_anchor": "领导之窗",
                "end_anchor": "内设机构",
                "include_selectors": ["div.news_item.ldzc ul.ldzc_ul li"],
                "exclude_selectors": ["网站导航", "友情链接", "页脚"],
            },
        },
        "api": {"enabled": False, "reason": "静态HTML领导卡片直接提供姓名、职务和详情链接"},
    },
}


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _is_hidden(node: Tag) -> bool:
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or "hidden" in classes:
            return True
        if "ldzc" in classes:
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("div.news_item.ldzc")
    if region is None or _is_hidden(region):
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select("ul.ldzc_ul li a[href]"):
        if _is_hidden(link):
            continue
        name_node = link.select_one("b")
        duty_node = link.select_one("span.zzz")
        name = re.sub(r"\s+", "", _clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").strip(" ：:，,。.；;")
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·.]{2,20}", name) or not duty or name in seen:
            continue
        detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_yunnan_ethnic_leader_window_cards_v1",
                "selector_summary": "div.news_item.ldzc；li卡片；b姓名；span.zzz职务；a[href]详情",
            }
        )
    return rows


def _official_alias_url(source_url: str) -> str:
    """旧域名中止连接时，仅切换到省民委当前官方别名域名并保留原路径。"""
    parsed = urlsplit(source_url)
    if parsed.hostname != "mzzj.yn.gov.cn":
        return source_url
    return urlunsplit((parsed.scheme, "mz.yn.gov.cn", parsed.path, parsed.query, parsed.fragment))


def main(output_dir: Path | None = None) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    import requests

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.naming import build_output_name
    from crawler_core.runner import make_failure_record, normalize_inline_rows, prepare_records_for_export

    rule = apply_business_source(PAGE_RULE)
    target_dir = output_dir or (project_dir / "outputs")
    output_path = target_dir / build_output_name(rule["rule_id"], rule["organization"])
    try:
        fetch_url = _official_alias_url(str(rule["url"]))
        response = requests.get(fetch_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        rows = normalize_inline_rows(rule, parse_page(response.text, response.url, rule))
        if not rows:
            raise RuntimeError("官方别名页面未解析到领导之窗记录")
        prepare_records_for_export(rows)
    except Exception as exc:
        failure = make_failure_record(rule, str(exc))
        failure.script_sequence = str(rule["rule_id"])
        rows = [failure]
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
