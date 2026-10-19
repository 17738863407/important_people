from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2989",
    "page_type": "人物目录详情页",
    "structure_group": "gx_health_list_detail_current_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#morelist ul.more-list",
    "name_selector": "#morelist ul.more-list li.article-re a[title][href]",
    "duty_selector": ".article-con .TRS_UEDITOR中的完整现任句",
    "detail_link_selector": "#morelist ul.more-list li.article-re a[title][href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "旧结果依赖本地详情文件；现按当前目录在线请求独立人物页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def _extract_current_sentence(html: str, name: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one(".article-con .TRS_UEDITOR") or soup.select_one(".article-con")
    if content is None:
        return "", ""
    text = _clean_text(content.get_text(" ", strip=True))
    if name not in re.sub(r"\s+", "", text):
        return "", ""
    match = re.search(r"现任[^。]*。", text)
    if match is None:
        return "", ""
    evidence = _clean_text(match.group(0))
    evidence = evidence.removeprefix("现任").strip().removesuffix("。")
    return evidence, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前领导目录顺序在线请求详情并提取完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    selector = "#morelist ul.more-list li.article-re a[title][href]"
    for link in soup.select(selector):
        name = re.sub(r"\s+", "", _clean_text(link.get("title") or link.get_text("", strip=True)))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            continue
        detail_url = urljoin(entry_url, str(link.get("href", "")))
        try:
            response = session.get(detail_url, timeout=25)
            response.raise_for_status()
        except requests.RequestException:
            continue
        response.encoding = response.apparent_encoding or response.encoding
        duty, evidence = _extract_current_sentence(response.text, name)
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": response.url,
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
