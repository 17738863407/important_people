from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3131",
    "page_type": "人物目录详情页",
    "structure_group": "lanzhou_healthcare_jpage_detail_ldzw_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内嵌JPage数据",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "raw_http",
    "parser": "page_lanzhou_healthcare_jpage_detail_ldzw_v1",
    "leader_region_selector": "div[id='75376'] script[type='text/xml'] record",
    "name_selector": "record CDATA a[title]",
    "duty_selector": "人物详情页.ldzw原始职务字段",
    "detail_link_selector": "record CDATA a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_to_detail",
        "detail_link_selector": "record CDATA a[href]",
        "detail_content_selector": ".ldzw",
        "max_detail_links": 15,
    },
    "risk_flag": "historical_script_hardcoded_seven_people_and_current_first_person_changed",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_datastore_selector": "div[id='75376'] script[type='text/xml']",
            "detail_content_selector": ".ldzw",
        },
        "api": {
            "enabled": False,
            "reason": "当前原始HTTP目录内嵌7个JPage record姓名链接，各在线详情页.ldzw直出职务",
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


def extract_detail_duty(detail_html: str, expected_name: str) -> str:
    """校验详情页属于当前姓名，并读取.ldzw原始职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = normalize_space(soup.title.get_text(" ", strip=True) if soup.title else "")
    container = soup.select_one(".ldzw")
    if expected_name not in re.sub(r"\s+", "", title) or container is None:
        return ""
    return normalize_space(container.get_text(" ", strip=True))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按JPage record顺序动态读取姓名链接及详情.ldzw职务。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="75376")
    datastore = (
        container.find("script", attrs={"type": "text/xml"})
        if container is not None
        else None
    )
    if datastore is None or not datastore.string:
        return []

    datastore_soup = BeautifulSoup(str(datastore.string), "html.parser")
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
    for record in datastore_soup.find_all("record"):
        fragment = BeautifulSoup(str(record.string or ""), "html.parser")
        link = fragment.find("a", href=True)
        if link is None:
            continue
        name = re.sub(
            r"\s+",
            "",
            normalize_space(str(link.get("title", "")) or link.get_text(" ", strip=True)),
        )
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            duty = extract_detail_duty(response.text, name)
        except requests.RequestException:
            continue
        if not duty:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "原始HTTP目录JPage datastore record顺序与动态姓名链接；详情页标题校验姓名后读取.ldzw原始职务",
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
