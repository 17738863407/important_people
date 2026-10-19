from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1487",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_public_resource_navigation_discovered_leader_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "site_navigation_discovery",
    "parser": "page_lanzhou_public_resource_navigation_discovered_leader_list_v1",
    "leader_region_selector": ".file-list .file-list-a",
    "name_selector": ".file-list-a a文本中--后的姓名",
    "duty_selector": ".file-list-a a文本中--前的职务",
    "detail_link_selector": ".file-list-a a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_list_links",
        "detail_link_selector": ".file-list-a a[href]",
        "max_detail_links": 30,
    },
    "risk_flag": "规则主表使用当前机构领导页；自定义直接运行仍保留同域导航发现作为入口变更兜底",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"[\s\u3000\xa0]+",
        " ",
        str(text or ""),
    ).strip()


def build_session() -> requests.Session:
    """创建可复用的当前官网HTTP会话。"""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    return session


def fetch_html(session: requests.Session, url: str) -> tuple[str, str]:
    """在线读取HTML并返回正文和最终URL。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text, response.url


def discover_current_leader_page(source_url: str) -> tuple[str, str]:
    """当旧入口失效时，沿同域官网导航动态发现当前机构领导页。"""
    session = build_session()
    try:
        source_html, source_final_url = fetch_html(session, source_url)
        if BeautifulSoup(source_html, "html.parser").select_one(".file-list .file-list-a a[href]"):
            return source_html, source_final_url
    except requests.RequestException:
        pass

    parsed = urlsplit(source_url)
    site_root = urlunsplit((parsed.scheme or "https", parsed.netloc, "/", "", ""))
    home_html, home_url = fetch_html(session, site_root)
    home_soup = BeautifulSoup(home_html, "html.parser")
    government_link = next(
        (
            link
            for link in home_soup.select("a[href]")
            if normalize_space(link.get_text(" ", strip=True)) == "政务信息"
        ),
        None,
    )
    if government_link is None:
        raise RuntimeError("同域官网首页未发现政务信息导航")

    government_html, government_url = fetch_html(
        session,
        urljoin(home_url, str(government_link.get("href", "")).strip()),
    )
    government_soup = BeautifulSoup(government_html, "html.parser")
    leader_links = [
        link
        for link in government_soup.select("a[href]")
        if normalize_space(link.get_text(" ", strip=True)) == "机构领导"
    ]
    candidate_urls = [
        urljoin(government_url, str(link.get("href", "")).strip())
        for link in leader_links
    ]
    current_record = next(
        (
            link
            for link in government_soup.select("a[href][title]")
            if re.fullmatch(
                r".+(?:书记|主任|调研员|巡视员)--[\u4e00-\u9fff·]{2,8}",
                normalize_space(str(link.get("title", ""))),
            )
        ),
        None,
    )
    if current_record is not None:
        record_url = urljoin(government_url, str(current_record.get("href", "")).strip())
        record_parts = urlsplit(record_url)
        leader_path = record_parts.path.rsplit("/", 2)[0] + "/govInfo.html"
        candidate_urls.append(
            urlunsplit(
                (
                    record_parts.scheme,
                    record_parts.netloc,
                    leader_path,
                    "",
                    "",
                )
            )
        )

    for candidate_url in dict.fromkeys(candidate_urls):
        try:
            candidate_html, candidate_final_url = fetch_html(session, candidate_url)
        except requests.RequestException:
            continue
        if BeautifulSoup(candidate_html, "html.parser").select_one(".file-list .file-list-a a[href]"):
            return candidate_html, candidate_final_url
    raise RuntimeError("同域官网政务信息导航未发现可验证的机构领导列表")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析当前机构领导列表中的“职务--姓名”记录。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in soup.select(".file-list .file-list-a a[href]"):
        text = normalize_space(link.get_text(" ", strip=True))
        if "--" not in text:
            continue
        duty, name = [normalize_space(part) for part in text.split("--", 1)]
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not re.search(r"书记|主任|调研员|巡视员", duty)
            or name in seen_names
        ):
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": urljoin(final_url, str(link.get("href", "")).strip()),
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "同域政务信息导航动态发现机构领导页；.file-list按网页顺序解析职务--姓名",
            }
        )
    if not rows:
        raise RuntimeError("当前机构领导页未发现可验证的职务姓名记录")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main(output_dir: Path | None) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.naming import build_output_name
    from crawler_core.rule_table import normalize_script_sequence
    from crawler_core.runner import (
        make_failure_record,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
    )

    rule = apply_business_source(PAGE_RULE)
    try:
        html, final_url = discover_current_leader_page(str(rule.get("url", "")))
        rows = normalize_inline_rows(rule, parse_page(html, final_url, rule))
        if not rows:
            rows = [make_failure_record(rule, "解析结果为空")]
    except Exception as error:
        rows = [make_failure_record(rule, str(error))]

    normalize_record_source_urls(rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        if not row.script_sequence:
            row.script_sequence = normalize_script_sequence(rule.get("rule_id"))

    output_name = build_output_name(str(rule.get("rule_id", "")), str(rule.get("organization", "机构")))
    output_path = (output_dir or project_dir / "outputs") / output_name
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    output_dir_value = None
    main(output_dir_value)
