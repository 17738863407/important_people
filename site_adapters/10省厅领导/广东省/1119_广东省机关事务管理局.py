from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1119",
    "page_type": "人物列表完整页",
    "structure_group": "gd_jgsw_aside_detail_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".aside",
    "name_selector": ".aside a[href]",
    "duty_selector": "detail .right.newsList",
    "detail_link_selector": ".aside a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "requests",
        "detail_content_selector": ".right.newsList",
        "max_detail_links": 50,
    },
    "risk_flag": "online误跟随正文location代码；职务仅取姓名前原文；首人链接等于入口页须置空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _fetch_duty(target: str, name: str) -> str:
    response = requests.get(target, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    scope = soup.select_one(".right.newsList")
    text = _clean_text(scope.get_text(" ", strip=True) if scope else "")
    if name not in text:
        return ""
    return text.split(name, 1)[0].strip(" ，,。；;：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧人物顺序在线抓取详情，并提取姓名前的原始职务。"""
    del page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".aside a[href]"):
        name = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        target = urljoin(final_url, link.get("href", ""))
        try:
            duty = _fetch_duty(target, name)
        except requests.RequestException:
            continue
        if not duty:
            continue
        seen.add(name)
        detail_url = "" if urldefrag(target)[0] == urldefrag(final_url)[0] else target
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
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
