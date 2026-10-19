from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0848",
    "page_type": "人物目录详情页",
    "structure_group": "上海国资委领导目录与机构职能页联动",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "playwright",
    "parser": "page_inline_shanghai_sasac_directory_v2",
    "leader_region_selector": ".gqzc_list_right > ul > li > a[href]",
    "risk_flag": "规则入口仅列姓名；职务从入口面包屑动态发现的同站机构职能页领导卡片取得",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    """去除姓名展示空格与列表圆点。"""
    return re.sub(r"\s+", "", clean_text(value).replace("•", ""))


def normalize_duty(value: str) -> str:
    """仅清理职务节点中的排版空白。"""
    duty = clean_text(value)
    return re.sub(r"\s*([、，,])\s*", r"\1", duty)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按规则入口目录顺序关联同站机构职能页中的领导职务强字段。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = final_url or str(page_rule.get("url", ""))
    directory: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".gqzc_list_right > ul > li > a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        detail_url = urljoin(source_url, str(link.get("href", "")))
        if name and name not in seen and "/shgzw_jgzn_gzwldjj/" in urlsplit(detail_url).path:
            seen.add(name)
            directory.append((name, detail_url))

    support_link = soup.select_one(".local a[title='机构职能'][href]")
    if not directory or support_link is None:
        return []

    from crawler_core.fetcher import fetch_by_playwright_subprocess

    support_url = urljoin(source_url, str(support_link.get("href", "")))
    support_result = fetch_by_playwright_subprocess(support_url)
    support_soup = BeautifulSoup(support_result.html, "html.parser")
    duty_by_detail: dict[str, tuple[str, str]] = {}
    for card in support_soup.select("#ldjj .idpage_person01"):
        name_node = card.select_one("b")
        duty_node = card.select_one("p")
        link_node = card.select_one("a[href]")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        duty = normalize_duty(duty_node.get_text(" ", strip=True) if duty_node else "")
        detail_url = urljoin(support_result.final_url or support_url, str(link_node.get("href", ""))) if link_node else ""
        if name and duty and detail_url:
            duty_by_detail[urlsplit(detail_url).path] = (name, duty)

    rows: list[dict[str, str]] = []
    for name, detail_url in directory:
        matched = duty_by_detail.get(urlsplit(detail_url).path)
        if matched is None or matched[0] != name:
            continue
        rows.append(
            {
                "name": name,
                "duty": matched[1],
                "detail_url": detail_url,
                "evidence": matched[1],
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "directory=.gqzc_list_right > ul > li > a[href]；duty=#ldjj .idpage_person01 p",
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
