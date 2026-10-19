from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3088",
    "page_type": "人物目录详情页",
    "structure_group": "lanzhou_project_review_leader_window_detail_parentheses_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_project_review_leader_window_detail_parentheses_v1",
    "leader_region_selector": ".zfxxgk_subtit文本为领导之窗的下一个zfxxgk_subcon",
    "name_selector": ".zfxxgk_subcon li a[href][title]",
    "duty_selector": "人物详情页#zoom姓名同志后括号原字段",
    "detail_link_selector": ".zfxxgk_subcon li a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_to_detail",
        "detail_link_selector": ".zfxxgk_subcon li a[href][title]",
        "detail_content_selector": "#zoom",
        "max_detail_links": 10,
    },
    "risk_flag": "online_detail_pages_required_and_raw_parenthesized_duty_preserved",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "group_heading_selector": ".zfxxgk_subtit",
            "name_link_selector": ".zfxxgk_subcon li a[href][title]",
            "detail_content_selector": "#zoom",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线领导之窗动态提供3个姓名链接，详情#zoom均有姓名同志（职务）原字段",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def find_leader_list(soup: BeautifulSoup):
    """以领导之窗标题为边界，排除同页机构设置分组。"""
    for heading in soup.select(".zfxxgk_subtit"):
        if normalize_space(heading.get_text(" ", strip=True)) == "领导之窗":
            return heading.find_next_sibling("div", class_="zfxxgk_subcon")
    return None


def extract_detail_fields(detail_html: str, expected_name: str) -> tuple[str, str]:
    """校验详情人物归属并保留姓名同志（职务）原字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    container = soup.select_one("#zoom")
    if container is None:
        return "", ""
    text = normalize_space(container.get_text(" ", strip=True))
    loose_name = r"\s*".join(re.escape(character) for character in expected_name)
    match = re.search(
        rf"(?P<evidence>{loose_name}同志[（(](?P<duty>[^）)]+)[）)])",
        text,
    )
    if not match:
        return "", ""
    return normalize_space(match.group("evidence")), normalize_space(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导之窗列表顺序逐个在线读取详情括号职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_list = find_leader_list(soup)
    if leader_list is None:
        return []

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in leader_list.select("li a[href][title]"):
        name = re.sub(r"\s+", "", normalize_space(str(link.get("title", ""))))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            evidence, duty = extract_detail_fields(response.text, name)
        except requests.RequestException:
            continue
        if not evidence or not duty:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导之窗分组列表DOM顺序与动态姓名链接；详情#zoom校验姓名后提取括号职务原字段",
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
