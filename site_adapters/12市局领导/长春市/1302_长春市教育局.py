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
    "rule_id": "1302",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_education_list_detail_gender_boundary_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_changchun_education_list_detail_gender_boundary_v1",
    "leader_region_selector": ".left_list li a[href]",
    "name_selector": "列表人物链接文本",
    "duty_selector": "同名详情正文中姓名与性别字段之间的原始职务",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".left_list"],
        "exclude_selectors": ["iframe"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": "a[href]",
        "detail_parser": "verified_name_to_gender_prefix_v1",
        "detail_name_selector": "#zoom .TRS_Editor段首",
        "detail_duty_selector": "姓名后至男/女字段前",
        "detail_content_selector": "#zoom .TRS_Editor",
        "max_detail_links": 20,
    },
    "risk_flag": "详情职务可能包含多个逗号分隔角色，必须以同名段首和性别字段共同划界",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_list_to_detail_gender_boundary",
    "locator": {
        "css": {
            "leader_region_selector": ".left_list li a[href]",
            "name_selector": "list_anchor_text",
            "detail_content_selector": "#zoom .TRS_Editor",
            "duty_selector": "detail_prefix_between_name_and_gender",
        },
        "api": {
            "enabled": False,
            "reason": "列表与人物详情均为静态HTML，详情段首直接包含姓名、职务和性别字段",
        },
        "migration": {
            "source": "legacy_inline_list_detail_parser",
            "verified_status": "verified_current_online_detail",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|调研员|纪检|组长|督学")
DETAIL_PATH_PATTERN = re.compile(r"/xxgk/jcxxgk/xdxx/\d{6}/t\d{8}_\d+\.html$")


def normalize_space(text: str) -> str:
    """压缩网页排版空白，不改变文字语义。"""
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """合并姓名中的排版空格。"""
    return re.sub(r"\s+", "", normalize_space(text))


def extract_detail_evidence(detail_html: str, expected_name: str) -> str:
    """核对详情段首姓名，并提取性别字段之前的完整原始职务。"""
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    content = detail_soup.select_one("#zoom .TRS_Editor") or detail_soup.select_one(".TRS_Editor")
    if content is None:
        return ""
    content_text = normalize_space(content.get_text(" ", strip=True))
    pattern = re.compile(
        rf"^{re.escape(expected_name)}[，,]\s*(?P<duty>.+?)[，,]\s*(?:男|女)[，,。]"
    )
    match = pattern.search(content_text)
    if match is None:
        return ""
    evidence = normalize_space(match.group("duty")).strip("，,。；; ")
    return evidence if DUTY_HINT_PATTERN.search(evidence) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持列表顺序，在线核对各详情段首姓名和完整职务。"""
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
        evidence = extract_detail_evidence(detail_result.html, name)
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
                    "strategy=custom_list_to_detail；leader=.left_list_links；"
                    "name=list_anchor；detail=same_host_xdxx_profile；"
                    "duty=verified_detail_prefix_between_name_and_gender"
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
