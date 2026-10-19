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
    "rule_id": "0362",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_finance_colon_title_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_finance_colon_title_cards_v1",
    "leader_region_selector": "ul.x_zcjd_li.mar0 > li",
    "name_selector": "a[href]标题冒号后文本",
    "duty_selector": "a[href]标题冒号前完整原文",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["ul.x_zcjd_li.mar0"],
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
    "risk_flag": "列表标题已含强结构职务与姓名；页面另含无关iframe",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_colon_title_cards",
    "locator": {
        "css": {
            "leader_region_selector": "ul.x_zcjd_li.mar0 > li",
            "title_link_selector": "a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "静态领导卡片标题已直接包含完整原始职务、姓名和详情链接",
        },
        "migration": {
            "source": "legacy_inline_title_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|纪检|组长")
DETAIL_PATH_PATTERN = re.compile(r"/zwgk/jggk/ldfg/\d{6}/t\d{8}_\d+\.html$")


def clean_text(text: str) -> str:
    """清理HTML排版空白，不改变网页文字语义。"""
    normalized = " ".join((text or "").replace("\xa0", " ").replace("\u3000", " ").split())
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", normalized)


def split_title(title: str) -> tuple[str, str]:
    """按卡片标题的明确冒号边界拆分完整原始职务和姓名。"""
    normalized = clean_text(title)
    parts = re.split(r"[：:]", normalized, maxsplit=1)
    if len(parts) != 2:
        return "", ""
    evidence = clean_text(parts[0])
    name = clean_text(parts[1]).replace(" ", "")
    if NAME_PATTERN.fullmatch(name) is None or DUTY_HINT_PATTERN.search(evidence) is None:
        return "", ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按可见卡片原序解析完整职务、姓名及同卡详情链接。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in soup.select(page_rule["leader_region_selector"]):
        link = item.select_one("a[href]")
        if link is None:
            continue
        name, evidence = split_title(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, clean_text(link.get("href", "")))
        parsed_url = urlsplit(detail_url)
        if (
            not name
            or not evidence
            or parsed_url.netloc.lower() != source_host
            or DETAIL_PATH_PATTERN.fullmatch(parsed_url.path) is None
        ):
            continue
        key = (name, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；leader=ul.x_zcjd_li.mar0 > li；"
                    "name=title_after_colon；duty=full_title_before_colon；"
                    "detail=same_card_same_host_link"
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
