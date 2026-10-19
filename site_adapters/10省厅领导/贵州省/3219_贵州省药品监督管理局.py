from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3219",
    "page_type": "人物目录详情页",
    "structure_group": "guizhou_drug_leader_details_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "directory_detail",
    "collector": "static_http",
    "parser": "parse_page",
    "leader_region_selector": ".ldzc_left",
    "name_selector": "a[href] > p.name",
    "duty_selector": "详情页 .ldzc_right .zw_name .zw",
    "detail_link_selector": "a[href]:has(p.name)",
    "content_scope": {
        "start_anchor": "领导之窗",
        "end_anchor": "",
        "include_selectors": [".ldzc_left", ".ldzc_right"],
        "exclude_selectors": [".ldfg"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "person_name_link",
        "detail_collector_type": "requests",
        "detail_link_selector": ".ldzc_left a[href]:has(p.name)",
        "detail_name_selector": ".ldzc_right .zw_name .name",
        "detail_duty_selector": ".ldzc_right .zw_name .zw",
        "detail_content_selector": ".ldzc_right .ldxx",
        "max_detail_links": 20,
    },
    "risk_flag": "入口右侧只显示默认首人；详情职务下方紧邻领导分工职责",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """确定性清理网页排版空白。"""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def _clean_name(value: str) -> str:
    """清理并校验中文姓名。"""
    name = re.sub(r"\s+", "", value)
    return name if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧目录顺序抓取每个详情页的姓名和职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select(".ldzc_left a[href]:has(p.name)"):
        name_node = link.select_one("p.name")
        name = _clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if (
            not name
            or urlparse(detail_url).netloc != urlparse(final_url).netloc
            or not re.fullmatch(r"/zwgk/ldzc1/\d{6}/t\d+_\d+\.html", urlparse(detail_url).path)
            or detail_url in seen_urls
        ):
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))
    if not candidates:
        raise RuntimeError("领导目录未解析出有效人物链接")

    rows: list[dict[str, str]] = []
    session = requests.Session()
    for expected_name, detail_url in candidates:
        response = session.get(detail_url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        block = detail_soup.select_one(".ldzc_right .ldxx")
        name_node = block.select_one(".zw_name .name") if block else None
        duty_node = block.select_one(".zw_name .zw") if block else None
        actual_name = _clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if actual_name != expected_name or not duty:
            raise RuntimeError(f"详情页姓名或职务字段无效：{expected_name}")
        rows.append(
            {
                "name": expected_name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": (
                    "strategy=css+requests；directory=.ldzc_left a[href]:has(p.name)；"
                    "detail=.ldzc_right .ldxx；name=.zw_name .name；duty=.zw_name .zw；"
                    "exclude=.ldfg领导分工"
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
