from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2422",
    "page_type": "人物目录详情页",
    "structure_group": "天津市审计局领导卡片分页目录",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_tianjin_audit_directory_v2",
    "leader_region_selector": ".ldxx-box > ul > li > a[href]",
    "risk_flag": "目录由脚本声明countPage并生成index_数字分页；第2页含王银柱且重复首位领导",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    """去除姓名节点中的展示空格。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_detail(url: str, session: requests.Session) -> tuple[str, str]:
    """在线取得同站人物详情页。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text, response.url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按分页目录DOM顺序逐页核名，并只提取详情正文第一条职务句。"""
    source_url = final_url or str(page_rule.get("url", ""))
    source_host = urlsplit(source_url).netloc.lower()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": source_url})

    page_count_match = re.search(r"var\s+countPage\s*=\s*(\d+)", html)
    page_count = int(page_count_match.group(1)) if page_count_match else 1
    directory_pages: list[tuple[str, str]] = [(html, source_url)]
    for page_index in range(1, page_count):
        page_url = urljoin(source_url, f"index_{page_index}.html")
        page_html, resolved_page_url = fetch_detail(page_url, session)
        directory_pages.append((page_html, resolved_page_url))

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for page_html, page_url in directory_pages:
        soup = BeautifulSoup(page_html, "html.parser")
        for link in soup.select(".ldxx-box > ul > li > a[href]"):
            name_node = link.select_one("p")
            name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
            detail_url = urljoin(page_url, str(link.get("href", "")))
            parsed = urlsplit(detail_url)
            if (
                re.fullmatch(r"[\u3400-\u9fff]{2,4}", name)
                and name not in seen
                and parsed.netloc.lower() == source_host
                and "/zwgk_146/jggk/ldxx/" in parsed.path
                and parsed.path.endswith(".html")
            ):
                seen.add(name)
                candidates.append((name, detail_url))

    rows: list[dict[str, str]] = []
    for name, detail_url in candidates:
        detail_html, resolved_url = fetch_detail(detail_url, session)
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        detail_name_node = detail_soup.select_one(".ldxx-deteail-img > p")
        detail_name = clean_name(detail_name_node.get_text(" ", strip=True) if detail_name_node else "")
        duty_scope = detail_soup.select_one(".ldxx-deteail .trs_editor_view")
        duty_text = clean_text(duty_scope.get_text(" ", strip=True) if duty_scope else "")
        duty_match = re.match(r"([^。]+。)", duty_text)
        if detail_name != name or duty_match is None:
            continue
        evidence = clean_text(duty_match.group(1)).removesuffix("。").strip()
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": resolved_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "directory=.ldxx-box > ul > li；detail_name=.ldxx-deteail-img > p；duty=.trs_editor_view首句",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
