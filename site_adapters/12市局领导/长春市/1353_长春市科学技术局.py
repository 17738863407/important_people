from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1353",
    "page_type": "人物目录详情页",
    "structure_group": "changchun_science_list_detail_labeled_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changchun_science_list_detail_labeled_fields_v1",
    "leader_region_selector": ".leftbox ul.currency_ul li a[href]",
    "name_selector": "列表人物链接文本及详情姓名字段",
    "duty_selector": "详情职务字段",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".leftbox ul.currency_ul"],
        "exclude_selectors": ["iframe"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": "a[href]",
        "detail_parser": "verified_labeled_name_duty_fields_v1",
        "detail_name_selector": ".TRS_Editor姓名字段",
        "detail_duty_selector": ".TRS_Editor职务字段",
        "detail_content_selector": ".TRS_Editor",
        "max_detail_links": 20,
    },
    "risk_flag": "详情字段标签和部分职务含排版空格，必须核对列表姓名并在工作分工或领导简介前截断",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail_labeled_fields",
    "locator": {
        "css": {
            "leader_region_selector": ".leftbox ul.currency_ul li a[href]",
            "name_selector": "list_anchor_and_detail_name_field",
            "duty_selector": "detail_duty_field",
            "detail_content_selector": ".TRS_Editor",
        },
        "api": {
            "enabled": False,
            "reason": "列表与人物详情均为静态HTML，详情正文具有姓名和职务标签字段",
        },
        "migration": {
            "source": "legacy_dynamic_page_rule_parser",
            "verified_status": "verified_current_online_detail",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|调研员|纪检|组长")
DETAIL_PATH_PATTERN = re.compile(r"/zzjg/ldxx/\d{6}/t\d{8}_\d+\.html$")
DETAIL_FIELDS_PATTERN = re.compile(
    r"姓\s*名[：:]\s*(?P<name>.*?)\s*职\s*务[：:]\s*(?P<duty>.*?)"
    r"(?:\s*工作分工[：:]|\s*领导简介[：:]|$)",
    re.S,
)


def normalize_space(text: str) -> str:
    """压缩网页排版空白，不改变文字语义。"""
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """合并姓名字段中的排版空格。"""
    return re.sub(r"\s+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    """仅清理职务字段中的排版空格和末尾句号。"""
    evidence = normalize_space(text)
    evidence = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", evidence)
    return evidence.rstrip("。. ")


def extract_detail(detail_html: str, expected_name: str) -> str:
    """核对详情姓名字段，并返回同一字段组的原始职务。"""
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    content = detail_soup.select_one(".TRS_Editor")
    if content is None:
        return ""
    content_text = normalize_space(content.get_text(" ", strip=True))
    match = DETAIL_FIELDS_PATTERN.search(content_text)
    if match is None or clean_name(match.group("name")) != expected_name:
        return ""
    evidence = clean_duty(match.group("duty"))
    return evidence if evidence and len(evidence) <= 90 and DUTY_HINT_PATTERN.search(evidence) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持列表顺序，在线核对详情姓名和职务字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for link in soup.select(page_rule["leader_region_selector"]):
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        parsed_url = urlsplit(detail_url)
        if (
            NAME_PATTERN.fullmatch(name) is None
            or parsed_url.netloc.lower() != source_host
            or DETAIL_PATH_PATTERN.fullmatch(parsed_url.path) is None
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        detail_result = fetch_html_with_strategy(detail_url, strategy="requests")
        evidence = extract_detail(detail_result.html, name)
        if not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_list_to_detail；leader=.currency_ul_links；"
                    "name=verified_detail_name_field；duty=detail_duty_field；"
                    "detail=same_host_ldxx_profile"
                ),
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
