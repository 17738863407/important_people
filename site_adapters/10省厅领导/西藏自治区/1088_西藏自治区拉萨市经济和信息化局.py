from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1088",
    "page_type": "多人物详情合并页",
    "structure_group": "lasa_iib_primary_and_member_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "custom_lasa_iib_primary_and_member_cards_v1",
    "leader_region_selector": ".content .container .kp.lead, .content .container .kp.ldlist li",
    "name_selector": ".kp.lead .info p.a a:first-of-type, .kp.ldlist li p:first-of-type",
    "duty_selector": ".kp.lead .info p.a a:nth-of-type(2), .kp.ldlist li p:nth-of-type(2)",
    "detail_link_selector": ".kp.lead .info p.a a:first-of-type[href], .kp.ldlist li > a[href]",
    "content_scope": {
        "start_anchor": "主要领导首卡",
        "end_anchor": "班子成员末卡",
        "include_selectors": [".content .container .kp.lead", ".content .container .kp.ldlist li"],
        "exclude_selectors": [".kp.lead .b", ".kp.lead .c"],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_item_dynamic_link",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".kp.lead .info p.a a:first-of-type[href], .kp.ldlist li > a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "主要领导卡片同时含分工与简历；只取p.a中的姓名和职务，随后连接班子成员列表，并保持网页原始标点",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".content .container .kp.lead, .content .container .kp.ldlist li",
            "name_selector": ".kp.lead p.a首链接或.ldlist首个p",
            "duty_selector": ".kp.lead p.a第二链接或.ldlist第二个p",
            "detail_link_selector": "对应人物卡片a[href]",
            "content_scope": {
                "start_anchor": "主要领导",
                "end_anchor": "班子成员末项",
                "include_selectors": [".kp.lead p.a", ".kp.ldlist li"],
                "exclude_selectors": ["我的分工", "我的简历"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML卡片与班子成员列表直接提供明确姓名、职务和详情链接",
        },
    },
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or ""))
    return text.strip()


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _append_row(
    rows: list[dict[str, str]],
    seen: set[str],
    name: str,
    duty: str,
    detail_url: str,
) -> None:
    cleaned_name = _clean_name(name)
    cleaned_duty = _clean_text(duty)
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", cleaned_name) or not cleaned_duty or cleaned_name in seen:
        return
    seen.add(cleaned_name)
    rows.append(
        {
            "name": cleaned_name,
            "duty": cleaned_duty,
            "detail_url": detail_url,
            "evidence": cleaned_duty,
            "parser": "custom_lasa_iib_primary_and_member_cards_v1",
            "selector_summary": ".kp.lead主要领导p.a；.kp.ldlist班子成员两个p",
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """先解析主要领导卡片，再按DOM顺序解析班子成员列表。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for card in soup.select(".content .container .kp.lead"):
        links = card.select(".info p.a a[href]")
        if len(links) < 2:
            continue
        _append_row(
            rows,
            seen,
            links[0].get_text(" ", strip=True),
            links[1].get_text(" ", strip=True),
            urljoin(base_url, str(links[0].get("href", ""))),
        )

    for link in soup.select(".content .container .kp.ldlist li > a[href]"):
        cells = link.select("p")
        if len(cells) < 2:
            continue
        _append_row(
            rows,
            seen,
            cells[0].get_text(" ", strip=True),
            cells[1].get_text(" ", strip=True),
            urljoin(base_url, str(link.get("href", ""))),
        )
    return rows


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
