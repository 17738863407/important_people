from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1318",
    "domain": "jyj.sft.fujian.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "fujian_prison_leader_detail_fields_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_fujian_prison_leader_detail_fields_v1",
    "leader_region_selector": ".main li.tree_item h3 a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "detail_content_selector": ".main",
        "detail_name_label": "姓名：",
        "detail_duty_start": "职务：",
        "detail_duty_end": "分工：",
    },
    "risk_flag": "领导目录与当前详情同页；职务必须限定在详情页职务字段至分工字段之间，入口页不得作为详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def comparable_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def extract_detail_record(detail_html: str, selector: str) -> tuple[str, str]:
    """提取详情页明确标注的姓名和职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for tag in soup.select("script, style"):
        tag.decompose()
    scope = soup.select_one(selector)
    if scope is None:
        return "", ""
    text = normalize_space(scope.get_text(" ", strip=True))
    match = re.search(r"姓名：\s*([\u4e00-\u9fff·\s]{2,8})\s+职务：\s*(.+?)\s+分工：", text)
    if match is None:
        return "", ""
    return clean_name(match.group(1)), normalize_space(match.group(2).strip("，,；; "))


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录原序在线取得详情页的姓名和职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    detail_selector = str(page_rule["detail_strategy"]["detail_content_selector"])
    entry_url = comparable_url(final_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        listed_name = clean_name(link.get_text(" ", strip=True))
        candidate = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", listed_name) or listed_name in seen:
            continue
        try:
            detail_html = html if comparable_url(candidate) == entry_url else fetch_detail_html(session, candidate)
        except requests.RequestException:
            continue
        name, evidence = extract_detail_record(detail_html, detail_selector)
        if name != listed_name or not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "" if comparable_url(candidate) == entry_url else candidate,
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
