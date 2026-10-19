from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0548",
    "domain": "fgw.hunan.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hunan_drc_list_to_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_hunan_drc_list_to_detail_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "详情页同时含职务与工作职责，仅提取职务字段；HTTPS异常时允许SSL降级",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_duty_evidence(value: str) -> str:
    """删除独立兼任状态标记，保留具体的兼任职务。"""
    return re.sub(r"(?:<\s*兼\s*>|[（(]\s*兼\s*[）)])", "", clean_text(value)).strip()


def fetch_html(session: requests.Session, url: str) -> tuple[str, str]:
    """在线抓取详情页；失败时重试并执行项目允许的SSL降级。"""
    last_error: requests.RequestException | None = None
    for attempt in range(3):
        try:
            if attempt:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = session.get(url, timeout=30, verify=not bool(attempt))
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text, response.url
        except requests.RequestException as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("详情页在线抓取未执行")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按机构领导列表顺序读取在线详情页姓名和职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    entry_host = urlparse(final_url).netloc.lower()
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".hy-list-text li a[title][href]"):
        expected_name = re.sub(r"\s+", "", str(link.get("title", "")))
        detail_url = urljoin(final_url, clean_text(str(link.get("href", ""))))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", expected_name):
            continue
        if urlparse(detail_url).netloc.lower() != entry_host:
            continue
        try:
            detail_html, detail_final_url = fetch_html(session, detail_url)
        except requests.RequestException:
            continue
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        title_node = detail_soup.select_one(".tys-main-zt h3, h3")
        name = re.sub(
            r"\s+",
            "",
            title_node.get_text(" ", strip=True) if isinstance(title_node, Tag) else "",
        )
        duty = ""
        for item in detail_soup.select("li.ldjs_com"):
            text = clean_text(item.get_text(" ", strip=True))
            match = re.match(r"^职\s*务\s*[:：]\s*(.+)$", text)
            if match:
                duty = clean_duty_evidence(match.group(1))
                break
        if name != expected_name or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；list=.hy-list-text li a[title][href]；detail=h3 + li.ldjs_com duty-field",
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
