from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1478",
    "page_type": "多人物详情合并页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".pic01, .side-menu",
    "row_selector": ".side-menu a[title]",
    "name_selector": ".pic01 h4",
    "duty_selector": ".pic01 p",
    "detail_link_selector": ".side-menu a[title][href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "medium",
    "risk": "各人物职务只在各自详情页；必须按侧栏顺序动态抓取详情，禁止固定姓名职务映射。当前入口对requests返回412，Playwright与Chrome CDP均取得过短防护页。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def canonical_url(url: str) -> str:
    """去除片段；目录路径补斜杠，文件型路径保持原样。"""
    parts = urlsplit(str(url or ""))
    path = parts.path
    if path and not path.endswith("/") and not re.search(r"/[^/]+\.[^/]+$", path):
        path = f"{path}/"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def parse_person_card(html: str, detail_url: str) -> dict[str, str] | None:
    """从单个人物详情页的明确卡片读取姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".pic01 h4")
    duty_node = soup.select_one(".pic01 p")
    name = normalize_text(name_node.get_text(" ", strip=True) if name_node is not None else "").replace(" ", "")
    duty = normalize_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return None
    return {"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按侧栏人物顺序动态抓取每个详情页并提取明确职务卡片。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    seen_urls: set[str] = set()
    current_url = canonical_url(final_url)

    for link in soup.select(".side-menu a[title][href]"):
        href = normalize_text(link.get("href", ""))
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        detail_url = canonical_url(urljoin(final_url, href))
        if detail_url not in seen_urls:
            candidates.append(detail_url)
            seen_urls.add(detail_url)

    if current_url and current_url not in seen_urls:
        candidates.insert(0, current_url)

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    failed_details: list[str] = []
    for detail_url in candidates:
        try:
            detail_html = (
                html
                if detail_url == current_url
                else fetch_html_with_strategy(detail_url, "online", force_browser=True).html
            )
            row = parse_person_card(detail_html, detail_url)
        except Exception as error:
            failed_details.append(f"{detail_url}：{error}")
            continue
        if row is None:
            failed_details.append(f"{detail_url}：缺少可验证的姓名或职务卡片")
            continue
        if row["name"] in seen_names:
            continue
        rows.append(row)
        seen_names.add(row["name"])

    if failed_details:
        raise RuntimeError("领导详情解析失败：" + "；".join(failed_details))
    return rows


def discover_current_leader_page(source_url: str) -> tuple[str, str]:
    """从规则主表网址的同源首页动态发现当前“领导信息”栏目。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    source = urlsplit(source_url)
    site_root = urlunsplit((source.scheme or "https", source.netloc, "/", "", ""))
    home_result = fetch_html_with_strategy(site_root, "online", force_browser=True)
    soup = BeautifulSoup(home_result.html, "html.parser")
    for link in soup.select("a[href]"):
        link_label = normalize_text(link.get("title", "")) or normalize_text(link.get_text(" ", strip=True))
        if link_label != "领导信息":
            continue
        leader_url = urljoin(home_result.final_url or site_root, str(link.get("href") or ""))
        if urlsplit(leader_url).netloc.lower() != source.netloc.lower():
            continue
        leader_result = fetch_html_with_strategy(leader_url, "online", force_browser=True)
        if "side-menu" not in leader_result.html or "pic01" not in leader_result.html:
            continue
        return leader_result.html, leader_result.final_url
    raise RuntimeError("官网首页未发现可验证的同源“领导信息”栏目")


def run_live(output_dir: Path | None = None) -> Path:
    """动态发现当前领导栏目，解析并按统一十三列契约导出。"""
    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.naming import build_output_name
    from crawler_core.runner import (
        make_failure_record,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    project_dir = resolve_project_dir()
    page_rule = apply_business_source(PAGE_RULE)
    try:
        html, final_url = discover_current_leader_page(str(page_rule["url"]))
        rows = normalize_inline_rows(page_rule, parse_page(html, final_url, page_rule))
        if not rows:
            rows = [make_failure_record(page_rule, "当前领导栏目解析结果为空")]
    except Exception as error:
        rows = [make_failure_record(page_rule, str(error))]

    normalize_record_source_urls(page_rule, rows)
    prepare_records_for_export(rows)
    target_dir = output_dir or (project_dir / "outputs")
    output_path = target_dir / build_output_name(str(page_rule["rule_id"]), str(page_rule["organization"]))
    export_records(output_path, rows)
    return output_path


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

    output_path = run_live()
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
