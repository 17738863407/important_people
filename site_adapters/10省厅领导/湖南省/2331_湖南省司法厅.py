from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2331",
    "domain": "sft.hunan.gov.cn",
    "page_type": "人物目录详情页",
    "structure_group": "",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_hunan_sft_online_details_v1",
    "leader_region_selector": "body",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "a[href*='ld']",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "body",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "a[href*='ld']",
            "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        },
        "api": {"enabled": False, "reason": "领导目录与人物详情页均在线静态 HTML 解析"},
    },
}


def _make_record(page_rule: dict, name: str, duty: str, evidence: str, detail_url: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url=detail_url,
        evidence=evidence,
        confidence="high",
        parser=page_rule["parser"],
    )


def _compact_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text).replace("\u3000", "")
    return re.sub(r"\s+", "", text).strip()


def _extract_duty(detail_html: str) -> tuple[str, str]:
    text = _compact_text(detail_html)
    current_match = re.search(r"现任(?P<duty>[^。]+)", text)
    if current_match:
        duty = current_match.group("duty").strip(" ：:")
        duty = re.sub(r"^职务\s*[：:]\s*", "", duty)
        return duty, duty
    duty_match = re.search(r"职务：(?P<duty>.*?)(?:工作职责|主管|分管|名称：|$)", text)
    duty = duty_match.group("duty").strip() if duty_match else ""
    return duty, duty


def _fetch_detail_html(detail_url: str) -> str:
    request = Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:
        fallback_url = detail_url.replace("https://sft.hunan.gov.cn/", "http://sft.hunan.gov.cn/", 1)
        with urlopen(Request(fallback_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在线解析湖南省司法厅领导目录及人物详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[object] = []
    seen_names: set[str] = set()
    for link in soup.select("a[href*='ld']"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        parsed_detail = urlparse(detail_url)
        if (
            parsed_detail.netloc.lower() != urlparse(final_url).netloc.lower()
            or "/jgld/" not in parsed_detail.path
            or not parsed_detail.path.lower().endswith((".shtml", ".html", ".htm"))
        ):
            continue
        try:
            duty, evidence = _extract_duty(_fetch_detail_html(detail_url))
        except Exception:
            continue
        if not duty:
            continue
        seen_names.add(name)
        rows.append(_make_record(page_rule, name, duty, evidence, detail_url))
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
