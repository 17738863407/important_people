from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3091",
    "page_type": "人物目录详情页",
    "structure_group": "mee_southwest_leader_directory_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "mee_southwest_leader_directory_details_v2",
    "leader_region_selector": ".main_left_nav2",
    "name_selector": ".lingdao .right > div > span",
    "duty_selector": ".lingdao .right > div > p",
    "detail_link_selector": ".main_left_nav2 a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_directory_details",
        "max_detail_links": 20,
    },
    "risk_flag": "领导目录与详情分离；职责正文不得作为职务依据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录DOM顺序发现详情页，并提取详情页明确标注的姓名与职务。"""
    import requests
    import urllib3
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    entry_host = urlparse(entry_url).netloc.lower()
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in region.select(page_rule["detail_link_selector"]):
        listed_name = _clean_text(link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(entry_url, href)
        parsed = urlparse(detail_url)
        if (
            not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", listed_name)
            or parsed.netloc.lower() != entry_host
            or "/jgzn/zxld/" not in parsed.path
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        candidates.append((listed_name, detail_url))

    if not candidates:
        return []

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    for listed_name, detail_url in candidates:
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        name_node = detail_soup.select_one(page_rule["name_selector"])
        duty_node = detail_soup.select_one(page_rule["duty_selector"])
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        duty = _clean_text(duty_node.get_text(" ", strip=True)) if duty_node else ""
        if name != listed_name or not duty:
            raise RuntimeError(f"人物详情字段无法与目录核对：{listed_name}")
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=response.url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
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
