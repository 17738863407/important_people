from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0980",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "site_channel_discovery",
    "parser": "page_hlj_department_management_current_article_v1",
    "leader_region_selector": "#detailContent",
    "row_selector": "机构领导正文中的中文序号人物块",
    "name_selector": "中文序号后、职务标签前姓名",
    "duty_selector": "职务标签与分工标签之间的完整原文",
    "detail_link_selector": "",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk_flag": "规则文章重定向省政府首页，须由入口栏目代码动态发现同栏当前机构正文；只接受含目标机构及机构领导章节的#detailContent。",
    "locator_strategy": "custom_parse_page",
}


def normalize_text(text: str) -> str:
    """仅压缩正文中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def fetch_html(session: requests.Session, url: str) -> tuple[str, str]:
    """在线读取HTML并返回正文和最终URL。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text, response.url


def is_target_article(html: str, organization: str) -> bool:
    """校验候选正文属于目标机构且包含机构领导章节。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#detailContent")
    if scope is None:
        return False
    text = normalize_text(scope.get_text(" ", strip=True))
    return organization in text and "一、机构领导" in text


def discover_current_article(source_url: str, organization: str) -> tuple[str, str]:
    """由规则入口栏目代码动态发现同栏当前机构正文。"""
    parsed = urlsplit(source_url)
    channel_match = re.search(r"/(c\d+)/", parsed.path, re.I)
    if not parsed.netloc or channel_match is None:
        raise RuntimeError("规则入口无法解析官网栏目代码")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    try:
        source_html, source_final_url = fetch_html(session, source_url)
        if is_target_article(source_html, organization):
            return source_html, source_final_url
    except requests.RequestException:
        pass

    channel_code = channel_match.group(1)
    prefix = parsed.path.split(f"/{channel_code}/", 1)[0]
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    list_url = urljoin(origin, f"{prefix}/{channel_code}/list.shtml")
    list_html, list_final_url = fetch_html(session, list_url)
    list_soup = BeautifulSoup(list_html, "html.parser")
    candidate_urls = [
        urljoin(list_final_url, str(link.get("href", "")).strip())
        for link in list_soup.select("a[href]")
        if re.search(rf"/{re.escape(channel_code)}/\d{{6}}/[^/]+\.shtml$", str(link.get("href", "")), re.I)
    ]
    for candidate_url in dict.fromkeys(candidate_urls):
        try:
            candidate_html, candidate_final_url = fetch_html(session, candidate_url)
        except requests.RequestException:
            continue
        if is_target_article(candidate_html, organization):
            return candidate_html, candidate_final_url
    raise RuntimeError("同栏当前列表未发现含机构领导章节的目标机构正文")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """只在机构概况目标正文的“机构领导”章节内提取人物。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one("#detailContent")
    if scope is None:
        return []
    text = normalize_text(scope.get_text(" ", strip=True))
    section_match = re.search(r"一、机构领导(.+?)(?:二、机构职能|二、主要职责|三、内设机构|$)", text)
    if section_match is None:
        return []

    rows: list[dict[str, str]] = []
    for match in re.finditer(
        r"（[一二三四五六七八九十]+）\s*([\u4e00-\u9fff·]{2,5})\s*职务\s*[：:]\s*(.+?)(?=\s*分工\s*[：:])",
        section_match.group(1),
    ):
        name = normalize_text(match.group(1))
        raw_duty = normalize_text(match.group(2))
        if not name or not raw_duty:
            continue
        evidence = raw_duty.removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name,
                "duty": raw_duty.removeprefix("现任").removesuffix("。"),
                "detail_url": "",
                "evidence": evidence,
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
        html, final_url = discover_current_article(
            str(rule.get("url", "")),
            str(rule.get("organization", "")),
        )
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

    output_name = build_output_name(rule.get("rule_id"), rule.get("organization"))
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
