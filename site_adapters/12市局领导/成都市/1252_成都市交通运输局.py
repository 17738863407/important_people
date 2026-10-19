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


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def extract_detail_path(onclick: str) -> str:
    """从人物卡片公开的 window.open 参数中提取详情相对路径。"""
    match = re.search(r"window\.open\(\s*['\"]([^'\"]+)['\"]", str(onclick or ""))
    return match.group(1).strip() if match else ""


def extract_detail_duty(detail_soup: BeautifulSoup, name: str) -> str:
    """提取详情页“职务：”标签后的第一个非空段落。"""
    duty_box = detail_soup.select_one("div.content #myFont")
    if duty_box is None:
        raise ValueError(f"{name}详情页未找到 div.content #myFont")

    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in duty_box.select(":scope > p")]
    paragraphs = [text for text in paragraphs if text]
    for index, text in enumerate(paragraphs[:-1]):
        if re.fullmatch(r"职务\s*[:：]", text):
            duty = paragraphs[index + 1].strip(" ：:，,。；;")
            if duty:
                return duty
    raise ValueError(f"{name}详情页未找到“职务：”后的职务段落")


def build_page_url(base_url: str, page_number: int) -> str:
    """根据页面自身分页编号构造同栏目分页 URL。"""
    page_url = re.sub(
        r"column-index-\d+\.shtml(?:\?.*)?$",
        f"column-index-{page_number}.shtml",
        base_url,
    )
    if page_url == base_url and page_number != 1:
        raise ValueError(f"无法从入口网址构造第 {page_number} 页")
    return page_url


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按公开分页和卡片 DOM 原始顺序抓取全部人物详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    first_soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    page_numbers = {
        int(button.get("value"))
        for button in first_soup.select("#pc-jgjs-zyld #page button.pageButton[value]")
        if str(button.get("value") or "").isdigit()
    }
    if not page_numbers:
        page_numbers = {1}

    people: list[tuple[str, str]] = []
    seen_detail_urls: set[str] = set()
    for page_number in sorted(page_numbers):
        if page_number == 1:
            page_soup = first_soup
        else:
            page_result = fetch_html_with_strategy(build_page_url(base_url, page_number), strategy="chrome")
            page_soup = BeautifulSoup(page_result.html, "html.parser")

        cards = page_soup.select("#pc-jgjs-zyld .html008 ul.list > li.myflex")
        if not cards:
            raise ValueError(f"第 {page_number} 页未找到人物卡片")
        for card in cards:
            name_node = card.select_one(":scope > .cont")
            name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
            detail_path = extract_detail_path(str(card.get("onclick") or ""))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not detail_path:
                continue
            detail_url = urljoin(base_url, detail_path)
            if detail_url in seen_detail_urls:
                continue
            seen_detail_urls.add(detail_url)
            people.append((name, detail_url))

    if not people:
        raise ValueError("全部公开分页均未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；leader=#pc-jgjs-zyld .html008 ul.list；"
        "name=li.myflex > .cont；duty=div.content #myFont中职务标签后段落；"
        "detail=li.myflex[onclick*=window.open]；pagination=#page button.pageButton[value]"
    )
    for name, detail_url in people:
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="chrome")
        except Exception as error:
            raise RuntimeError(f"{name}详情页采集失败：{error}") from error
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        duty = extract_detail_duty(detail_soup, name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_chengdu_transport_paged_detail_v1",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1252",
    "page_type": "人物列表完整页",
    "structure_group": "chengdu_gkml_ldcy_paged_detail",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_chengdu_transport_paged_detail_v1",
    "leader_region_selector": "#pc-jgjs-zyld .html008 ul.list",
    "name_selector": "li.myflex > .cont",
    "duty_selector": "div.content #myFont > p",
    "detail_link_selector": "li.myflex[onclick*='window.open']",
    "detail_strategy": {"required": False, "mode": "inline_paged_detail_fetch"},
    "risk_flag": "站点HTTP请求返回412且无头Playwright结果无效；人物目录存在多页，必须按页面公开页码完整遍历",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#pc-jgjs-zyld .html008 ul.list",
            "name_selector": "li.myflex > .cont",
            "duty_selector": "div.content #myFont > p",
            "detail_link_selector": "li.myflex[onclick*='window.open']",
        },
        "api": {
            "enabled": False,
            "reason": "当前领导分页、人物链接和详情职务均由浏览器渲染DOM稳定提供",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


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
