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
    "rule_id": "1273",
    "page_type": "人物列表完整页",
    "structure_group": "changchun_urban_construction_double_dash_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_changchun_urban_construction_double_dash_links_v1",
    "leader_region_selector": "#con_one_1 ul.x_zcjd_li.mar0 > li > a[href]",
    "name_selector": "链接标题双连字符后姓名",
    "duty_selector": "链接标题双连字符前完整原文",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["#con_one_1 ul.x_zcjd_li.mar0"],
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
    "risk_flag": "全页链接较多，必须限定负责人简介容器；标题职务包含完整机构前缀",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "page_inline_double_dash_detail_links",
    "locator": {
        "css": {
            "leader_region_selector": "#con_one_1 ul.x_zcjd_li.mar0 > li > a[href]",
            "name_selector": "title_after_double_dash",
            "duty_selector": "full_title_before_double_dash",
            "detail_link_selector": "same_anchor_href",
        },
        "api": {
            "enabled": False,
            "reason": "静态负责人链接标题已包含完整职务、姓名和人物详情链接",
        },
        "migration": {
            "source": "legacy_inline_double_dash_parser",
            "verified_status": "verified_current_online",
            "behavior_changed": True,
        },
    },
}


NAME_PATTERN = re.compile(r"[\u4e00-\u9fff·]{2,6}")
DUTY_HINT_PATTERN = re.compile(r"党组|党委|局长|主任|书记|成员|巡视员|调研员|纪检|组长")
DETAIL_PATH_PATTERN = re.compile(r"/zwgk/fzrjj/\d{6}/t\d{8}_\d+\.html$")


def normalize_space(text: str) -> str:
    """压缩网页排版空白，不改变文字语义。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", text or "").strip()


def parse_title(title: str) -> tuple[str, str]:
    """按链接标题双连字符拆分完整原始职务和姓名。"""
    normalized = normalize_space(title)
    if "--" not in normalized:
        return "", ""
    evidence, name_text = normalized.split("--", 1)
    evidence = normalize_space(evidence).strip("，,、；;：:。")
    name = re.sub(r"\s+", "", name_text)
    if NAME_PATTERN.fullmatch(name) is None or DUTY_HINT_PATTERN.search(evidence) is None:
        return "", ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按负责人列表顺序提取完整职务、姓名和同链接详情页。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source_host = urlsplit(final_url).netloc.lower()
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(page_rule["leader_region_selector"]):
        name, evidence = parse_title(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        parsed_url = urlsplit(detail_url)
        if (
            not name
            or not evidence
            or parsed_url.netloc.lower() != source_host
            or DETAIL_PATH_PATTERN.fullmatch(parsed_url.path) is None
            or name in seen
        ):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "source_text": evidence,
                "method": page_rule["parser"],
                "note": (
                    "strategy=custom_parse_page；leader=#con_one_1_leader_links；"
                    "name=title_after_double_dash；duty=full_title_before_double_dash；"
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
