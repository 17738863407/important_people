from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1237",
    "page_type": "人物列表完整页",
    "structure_group": "wuhan_transport_online_detail_duty_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_transport_online_detail_duty_v2",
    "leader_region_selector": ".leader h4 a[href]",
    "name_selector": ".leader h4 a[href]",
    "duty_selector": "在线详情页.leader-info中职务至分工边界",
    "detail_link_selector": ".leader h4 a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "online_detail_field",
        "detail_link_selector": ".leader h4 a[href]",
        "detail_content_selector": ".leader-info",
        "max_detail_links": 20,
    },
    "risk_flag": "原始响应直接含人物链接；online编码误判会导致姓名乱码，入口固定raw_http并在线抓取详情职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性合并详情页字段排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_entry_soup(html: str) -> BeautifulSoup:
    """必要时严格回转HTTP头缺少charset造成的UTF-8乱码。"""
    soup = BeautifulSoup(html or "", "html.parser")
    links = soup.select(".leader h4 a[href]")
    names = [re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True))) for link in links]
    if links and not any(re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) for name in names):
        try:
            repaired_html = (html or "").encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"入口页UTF-8乱码严格回转失败：{exc}") from exc
        soup = BeautifulSoup(repaired_html, "html.parser")
    return soup


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """在线读取人物详情页，并保留有限重试的完整错误链。"""
    errors: list[str] = []
    for attempt in range(1, 4):
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            errors.append(f"第{attempt}次：{type(exc).__name__}: {exc}")
    raise RuntimeError(f"在线详情页抓取失败：{detail_url}；{'；'.join(errors)}")


def extract_detail_duty(detail_html: str, name: str) -> str:
    """从当前人物详情页唯一职务字段中提取完整原文。"""
    soup = BeautifulSoup(detail_html or "", "html.parser")
    regions = soup.select(".leader-info")
    if len(regions) != 1:
        raise RuntimeError(f"详情页leader-info数量异常：{name} {len(regions)}")
    text = clean_text(regions[0].get_text(" ", strip=True))
    match = re.search(r"职\s*务\s*(?P<evidence>.+?)\s*分\s*工(?:\s|$)", text)
    if match is None:
        raise RuntimeError(f"详情页职务/分工边界异常：{name} {text}")
    evidence = clean_text(match.group("evidence")).strip("，,；;。 ")
    evidence = re.sub(r"[（(]\s*兼\s*[）)]\s*(?=\S)", "，", evidence)
    evidence = re.sub(r"[（(]\s*兼\s*[）)]", "", evidence).strip("，,；;。 ")
    if not evidence:
        raise RuntimeError(f"详情页职务字段为空：{name}")
    return evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按入口页人物顺序在线读取详情页职务字段。"""
    from crawler_core.models import PersonRecord

    soup = parse_entry_soup(html)
    links = soup.select(".leader h4 a[href]")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    records: list[object] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    for link in links:
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        detail_url = urljoin(final_url, link.get("href", "").strip())
        parts = urlsplit(detail_url)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) is None:
            raise RuntimeError(f"入口页人物姓名异常：{name}")
        if parts.scheme not in {"http", "https"} or not parts.netloc or detail_url == final_url:
            raise RuntimeError(f"入口页人物详情链接异常：{name} {detail_url}")
        if name in seen_names or detail_url in seen_links:
            raise RuntimeError(f"入口页人物姓名或链接重复：{name} {detail_url}")
        evidence = extract_detail_duty(fetch_detail_html(session, detail_url), name)
        seen_names.add(name)
        seen_links.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("入口页没有可验证人物详情链接")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
