from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1692",
    "page_type": "人物列表完整页",
    "structure_group": "gd_mpa_gkmlpt_api_detail_prefix_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_to_detail",
    "collector": "raw_http_api",
    "parser": "builtin_parse_page",
    "leader_region_selector": "API articles[]",
    "name_selector": "articles[].title",
    "duty_selector": "detail .content姓名前文本",
    "detail_link_selector": "articles[].post_url",
    "detail_strategy": {
        "required": True,
        "mode": "api_to_detail",
        "detail_collector_type": "requests",
        "detail_content_selector": ".content",
        "max_detail_links": 50,
    },
    "api": {
        "enabled": True,
        "endpoint": "https://mpa.gd.gov.cn/gkmlpt/api/all/2373?page=1&sid=206",
        "method": "GET",
        "data_path": "articles",
        "name_field": "title",
        "detail_field": "post_url",
    },
    "risk_flag": "详情简介为职务+姓名+履历，职务仅取姓名前连续原文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _fetch_articles(page_rule: dict) -> list[dict]:
    response = requests.get(
        str(page_rule["api"]["endpoint"]),
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    return list(response.json().get("articles", []))


def _fetch_detail(target: str, name: str) -> tuple[str, str]:
    response = requests.get(target, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    scope = soup.select_one(".content")
    text = _clean_text(scope.get_text(" ", strip=True) if scope else "")
    if name not in text:
        return "", ""
    duty = text.split(name, 1)[0].strip(" ，,。；;：:")
    return duty, response.url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按接口数组顺序在线抓取详情并提取姓名前原始职务。"""
    del html, final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for article in _fetch_articles(page_rule):
        name = re.sub(r"\s+", "", _clean_text(str(article.get("title", ""))))
        target = str(article.get("post_url") or "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not target or name in seen:
            continue
        try:
            duty, detail_url = _fetch_detail(target, name)
        except requests.RequestException:
            continue
        if not duty:
            continue
        seen.add(name)
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
