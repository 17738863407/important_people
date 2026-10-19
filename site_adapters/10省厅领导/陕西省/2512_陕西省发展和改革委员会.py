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


PAGE_RULE = {
    "rule_id": "2512",
    "page_type": "人物列表完整页",
    "structure_group": "leader_list_to_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "ShaanxiDrcLeaderDetailParser_v1",
    "leader_region_selector": "a[href*='/wld/ldxx/']",
    "name_selector": "列表链接文本",
    "duty_selector": ".ld-rt p第二项",
    "detail_link_selector": "a[href*='/wld/ldxx/']",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_name_selector": ".ld-rt p:first-of-type",
        "detail_duty_selector": ".ld-rt p:nth-of-type(2)",
    },
    "confidence": "high",
    "risk_flag": "列表只直出姓名，职务必须从当前动态详情页取得；禁止读取本地详情快照",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """保持委领导列表顺序，逐个从详情页提取当前职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = str(link.get("href", ""))
        if "/wld/ldxx/" not in href:
            continue
        list_name = _clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", list_name) or list_name in seen:
            continue
        detail_url = urljoin(base_url, href)
        try:
            detail_result = fetch_html_with_strategy(detail_url, "raw_http")
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        except Exception:
            continue

        fields = detail_soup.select(".ld-rt p")
        if len(fields) < 2:
            continue
        detail_name = _clean_name(fields[0].get_text(" ", strip=True))
        duty = _clean_text(fields[1].get_text(" ", strip=True))
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty).strip(" ，,。；;：: ")
        if detail_name != list_name or not duty:
            continue

        seen.add(list_name)
        records.append(
            {
                "name": list_name,
                "duty": "",
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "列表=a[href含/wld/ldxx/]；详情姓名=.ld-rt p[0]；详情职务=.ld-rt p[1]",
                "order": str(len(records) + 1),
            }
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
