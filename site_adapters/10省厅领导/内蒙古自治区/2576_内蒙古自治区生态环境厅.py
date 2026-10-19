from __future__ import annotations

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
    "rule_id": "2576",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "enhanced_http",
    "parser": "custom_inner_mongolia_ecology_list_to_detail_v1",
    "leader_region_selector": ".X_S1 > .container",
    "name_selector": ".leader1_box .fl_l > a, .X_S1 > .container > .fl_r li a > p",
    "duty_selector": "#djh_ldleft .ld > h3",
    "detail_link_selector": ".leader1_box .fl_l > a[href], .X_S1 > .container > .fl_r li > a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_collector_type": "requests"},
    "risk_flag": "入口主要负责人卡片与其他厅领导卡片分列，职务需从对应详情页取得",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """清理页面排版空白，不改变原始语义。"""
    return " ".join(value.split())


def _clean_current_evidence(value: str) -> str:
    """仅删除已定位现职句句首的“现任”固定标签。"""
    prefix = "现任职务" if value.startswith("现任职务") else "现任"
    return value[len(prefix) :].lstrip(" ：:")


def _parse_detail_page(html: str, detail_url: str, expected_name: str) -> dict[str, str] | None:
    """从当前人物详情页提取明确姓名、原始职务和完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one("#djh_ldleft .fly_title_ldxm")
    name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
    if not name or name != expected_name:
        return None

    heading = soup.select_one("#djh_ldleft .ld > h3")
    heading_text = _clean_text(heading.get_text(" ", strip=True) if heading else "")
    duty = heading_text[:-len(name)].strip() if heading_text.endswith(name) else ""

    evidence = ""
    for paragraph in soup.select("#djh_ldright .cont2 p"):
        paragraph_text = _clean_text(paragraph.get_text(" ", strip=True))
        if paragraph_text.startswith("现任"):
            evidence = _clean_current_evidence(paragraph_text)
            break
    if not duty or not evidence:
        return None

    return {
        "name": name,
        "duty": duty,
        "detail_url": detail_url,
        "evidence": evidence,
        "selector_summary": "入口.X_S1人物链接；详情#djh_ldleft姓名/职务；#djh_ldright .cont2现任句",
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口 DOM 顺序发现全部厅领导，并从对应详情页取得现任职务证据。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    primary_link = soup.select_one(".X_S1 .leader1_box > .fl_l > a[href]")
    primary_text = _clean_text(primary_link.get_text(" ", strip=True) if primary_link else "")
    if primary_link and "：" in primary_text:
        primary_name = _clean_text(primary_text.split("：", 1)[0]).replace(" ", "")
        primary_url = urljoin(final_url, str(primary_link.get("href", "")))
        if primary_name and primary_url:
            candidates.append((primary_name, primary_url))
            seen_urls.add(primary_url)

    for detail_link in soup.select(".X_S1 > .container > .fl_r > ul > li > a[href]"):
        name_node = detail_link.select_one("p")
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        detail_url = urljoin(final_url, str(detail_link.get("href", "")))
        if not name or not detail_url or detail_url in seen_urls:
            continue
        candidates.append((name, detail_url))
        seen_urls.add(detail_url)

    rows: list[dict[str, str]] = []
    for expected_name, detail_url in candidates:
        detail_result = fetch_html_with_strategy(detail_url, strategy="requests")
        row = _parse_detail_page(detail_result.html, detail_result.final_url, expected_name)
        if row is None:
            raise RuntimeError(f"详情页缺少可验证姓名或现任职务：{detail_url}")
        rows.append(row)
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
