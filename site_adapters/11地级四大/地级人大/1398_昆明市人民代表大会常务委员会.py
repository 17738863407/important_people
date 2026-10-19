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
    "rule_id": "1398",
    "page_type": "人物目录详情页",
    "structure_group": "kunming_renda_leader_detail_first_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "kunming_renda_leader_detail_first_duty_v1",
    "leader_region_selector": ".list_txtsbg",
    "name_selector": "li a.ui-float-left[href]",
    "duty_selector": ".txtcen p",
    "detail_link_selector": "li a.ui-float-left[href]",
    "content_scope": {
        "include_selectors": [".list_txtsbg"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_link_selector": "li a.ui-float-left[href]",
        "detail_name_selector": ".timu",
        "detail_duty_selector": ".txtcen p",
        "max_detail_links": 50,
    },
    "risk_flag": "详情首段职务后紧接分工说明，只取首个标点前的明确职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value)).strip()


def _clean_duty(value: str) -> str:
    duty = _clean_text(value)
    duty = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", duty)
    return duty.rstrip("。.")


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def _fetch_detail_duty(detail_url: str, referer_url: str) -> str:
    response = requests.get(
        detail_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": referer_url},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    for paragraph in soup.select(".txtcen p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        return _clean_duty(re.split(r"[，,。；;]", text, maxsplit=1)[0])
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录顺序抓取人物详情页，并提取首段明确职务前缀。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".list_txtsbg")
    if region is None:
        return []

    entry_url = page_rule["url"]
    records: list[object] = []
    seen: set[str] = set()
    for anchor in region.select("li a.ui-float-left[href]"):
        name = _clean_name(anchor.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,15}", name):
            continue
        href = anchor.get("href", "").strip()
        detail_url = urljoin(final_url, href)
        if (
            not href
            or href.startswith(("#", "javascript:", "mailto:"))
            or _normalize_url(detail_url) == _normalize_url(entry_url)
        ):
            continue
        duty = _fetch_detail_duty(detail_url, final_url)
        if not duty or len(duty) > 120:
            continue
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=entry_url,
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary=".list_txtsbg目录 + 详情.txtcen首个非空段落职务前缀",
            )
        )
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
