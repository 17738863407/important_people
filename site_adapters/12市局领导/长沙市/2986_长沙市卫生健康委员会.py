from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2986",
    "page_type": "人物目录详情页",
    "structure_group": "changsha_health_leader_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "leader_region_selector": "a[href^='./20']",
    "name_selector": "a[href^='./20']",
    "detail_link_selector": "a[href^='./20']",
    "risk_flag": "详情页同时含工作分工和简历，仅接受明确标注的职务字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _detail_duty(detail_soup: BeautifulSoup) -> str:
    for block in detail_soup.select("div.leader-main div.wrap_right > dl"):
        heading = block.select_one("h2")
        if heading is None or _compact_text(heading.get_text(" ", strip=True)) != "职务":
            continue
        values = block.find_all("dd", recursive=False)
        if len(values) < 2:
            break
        return " ".join(values[1].get_text(" ", strip=True).replace("\xa0", " ").split())
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录原始顺序在线读取详情页的明确职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select("a[href^='./20']"):
        name = _compact_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[一-鿿·]{2,4}", name) or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    for name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        title = detail_soup.select_one("h2.leader-tit")
        detail_name = _compact_text(title.get_text(" ", strip=True) if title else "")
        if detail_name != name:
            raise RuntimeError(f"目录姓名与详情姓名不一致：{name} / {detail_name}")
        evidence = _detail_duty(detail_soup)
        if not evidence:
            raise RuntimeError(f"详情页缺少明确职务字段：{detail_url}")
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": response.url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_changsha_health_leader_details_v1",
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
