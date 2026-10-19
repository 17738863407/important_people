from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1748",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_civil_affairs_name_duty_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_civil_affairs_name_duty_links_v1",
    "leader_region_selector": ".leftbox_table1 a[href]",
    "name_selector": "链接文本首个职务提示词前姓名",
    "duty_selector": "链接文本首个职务提示词起的原始职务",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".leftbox_table1"],
        "exclude_selectors": ["iframe"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href]",
        "detail_parser": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
    },
    "risk_flag": "姓名内部可能含排版空格，必须限定领导表格并以明确职务提示词划界",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_name_before_duty_hint_links",
    "locator": {
        "css": {
            "leader_region_selector": ".leftbox_table1 a[href]",
            "name_selector": "text_before_first_duty_hint",
            "duty_selector": "text_from_first_duty_hint",
            "detail_link_selector": "same_anchor_href",
        },
        "api": {
            "enabled": False,
            "reason": "静态领导链接文本已直接包含姓名、职务和详情页",
        },
        "migration": {
            "source": "legacy_inline_duty_hint_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_START_PATTERN = re.compile(r"党组|党委|局长|副局长|主任|书记|巡视员|调研员|纪检|组长")
DETAIL_PATH_PATTERN = re.compile(r"/xxgk/jcxx/ldxx/\d{6}/t\d{8}_\d+\.html$")


def clean_text(text: str) -> str:
    """压缩页面排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def split_line(text: str) -> tuple[str, str]:
    """按首个明确职务提示词拆分姓名与原始职务。"""
    normalized = clean_text(text)
    match = DUTY_START_PATTERN.search(normalized)
    if match is None:
        return "", ""
    name = re.sub(r"\s+", "", normalized[: match.start()])
    evidence = clean_text(normalized[match.start() :])
    if NAME_PATTERN.fullmatch(name) is None or not evidence:
        return "", ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导链接原序提取姓名、原始职务和同链接详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for link in soup.select(page_rule["leader_region_selector"]):
        name, evidence = split_line(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        parsed_url = urlsplit(detail_url)
        if (
            not name
            or not evidence
            or parsed_url.netloc.lower() != source_host
            or DETAIL_PATH_PATTERN.fullmatch(parsed_url.path) is None
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；leader=.leftbox_table1_links；"
                    "name=before_first_duty_hint；duty=from_first_duty_hint；"
                    "detail=same_anchor_same_host_profile"
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
