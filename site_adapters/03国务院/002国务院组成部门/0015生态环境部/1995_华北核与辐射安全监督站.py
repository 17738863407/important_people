from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

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
    "rule_id": "1995",
    "page_type": "人物目录详情页",
    "structure_group": "nro_leader_list_to_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_nro_leader_list_to_detail_v2",
    "leader_region_selector": ".main a[href*='.shtml']",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": ".main a[href*='.shtml']",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".main"],
        "exclude_selectors": ["script", "style"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".main a[href*='.shtml']",
        "detail_parser": "page_inline_nro_leader_detail_v2",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": ".TRS_Editor",
        "max_detail_links": 20,
    },
    "risk_flag": "详情正文有两种结构；姓名链接顺序必须继承目录DOM，职务只能从对应详情正文开头提取",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail",
    "locator": {
        "css": {
            "leader_region_selector": ".main a[href*='.shtml']",
            "detail_link_selector": ".main a[href*='.shtml']",
            "detail_content_selector": ".TRS_Editor",
        },
        "api": {"enabled": False, "reason": "当前目录和人物详情页静态HTML提供权威字段"},
        "migration": {
            "source": "legacy_fixed_people_and_offline_detail_dependency_removed",
            "verified_status": "verified_current_raw_http_details",
            "behavior_changed": True,
        },
    },
}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _fetch_detail(session: requests.Session, url: str) -> str:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    errors: list[str] = []
    for _ in range(6):
        try:
            response = session.get(url, timeout=25, verify=False)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            errors.append(str(exc))
    raise RuntimeError(f"人物详情页抓取失败：{url}；{' | '.join(errors)}")


def _parse_detail(html: str, name: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".TRS_Editor")
    if content is None:
        return "", ""
    text = _clean_text(content.get_text(" ", strip=True))
    if not text.startswith(name):
        return "", ""
    remainder = text[len(name) :].strip()
    second_name = remainder.find(name)
    if second_name > 0:
        duty = remainder[:second_name].strip(" ，,；;")
        return duty, duty
    sentence_match = re.match(r"([^。]*?任([^。]+)。)", remainder)
    if sentence_match is None:
        return "", ""
    duty = _clean_text(sentence_match.group(2))
    evidence = _clean_text(sentence_match.group(1)).removesuffix("。").rstrip()
    return duty, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """动态遍历目录链接，并从每个人物自己的详情正文提取职务。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145 Safari/537.36",
            "Referer": final_url,
        }
    )
    records: list[PersonRecord] = []
    seen_urls: set[str] = set()
    for link in soup.select(".main a[href*='.shtml']"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, link.get("href", ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,20}", name) or detail_url in seen_urls:
            continue
        detail_html = _fetch_detail(session, detail_url)
        duty, evidence = _parse_detail(detail_html, name)
        if not duty:
            continue
        seen_urls.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="目录.main人物链接 + 详情.TRS_Editor开头",
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
