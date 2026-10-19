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
    "rule_id": "1707",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_ethnic_affairs_nested_inner_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_ethnic_affairs_nested_inner_links_v1",
    "leader_region_selector": "ul.list_right_bar_zjdc > li > a[href] > a[href]",
    "name_selector": "内层链接标题冒号后姓名",
    "duty_selector": "内层链接标题冒号前原始职务",
    "detail_link_selector": "内层a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["ul.list_right_bar_zjdc"],
        "exclude_selectors": ["iframe", "span.data"],
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
    "risk_flag": "列表HTML含嵌套a，外层链接文本混入发布日期并造成重复，必须选内层人物链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_nested_inner_colon_links",
    "locator": {
        "css": {
            "leader_region_selector": "ul.list_right_bar_zjdc > li > a[href] > a[href]",
            "name_selector": "inner_title_after_colon",
            "duty_selector": "inner_title_before_colon",
            "detail_link_selector": "inner_anchor_href",
        },
        "api": {
            "enabled": False,
            "reason": "静态列表内层人物链接已包含职务、姓名和详情页",
        },
        "migration": {
            "source": "legacy_inline_colon_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|调研员|纪检|组长")
DETAIL_PATH_PATTERN = re.compile(r"/ldcy/jbxx/\d{6}/t\d{8}_\d+\.html$")


def clean_text(text: str) -> str:
    """压缩页面排版空白，不改变网页文字语义。"""
    return " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())


def split_title(title: str) -> tuple[str, str]:
    """按内层人物链接标题的明确冒号拆分职务和姓名。"""
    parts = re.split(r"[：:]", clean_text(title), maxsplit=1)
    if len(parts) != 2:
        return "", ""
    evidence = clean_text(parts[0]).strip("，,、；;。")
    name = re.sub(r"\s+", "", parts[1])
    if NAME_PATTERN.fullmatch(name) is None or DUTY_HINT_PATTERN.search(evidence) is None:
        return "", ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按列表原序解析内层人物链接，排除外层日期与重复。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for link in soup.select(page_rule["leader_region_selector"]):
        name, evidence = split_title(link.get_text(" ", strip=True))
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
                    "strategy=custom_parse_page；leader=nested_inner_person_links；"
                    "name=inner_title_after_colon；duty=inner_title_before_colon；"
                    "outer_date_and_duplicates=excluded"
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
