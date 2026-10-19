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
    "rule_id": "0698",
    "page_type": "人物列表完整页",
    "structure_group": "gd_gkmlpt_api_detail_duty_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "api_to_detail",
    "collector": "online_http_api",
    "parser": "builtin_parse_page",
    "leader_region_selector": "API articles[]",
    "name_selector": "articles[].title",
    "duty_selector": "detail #zw p",
    "detail_link_selector": "articles[].post_url",
    "detail_strategy": {
        "required": True,
        "mode": "api_to_detail",
        "detail_collector_type": "requests",
        "detail_content_selector": "#zw",
        "max_detail_links": 50,
    },
    "api": {
        "enabled": True,
        "endpoint": "https://gdwsxf.gd.gov.cn/gkmlpt/api/all/2853?page=1&sid=248",
        "method": "GET",
        "data_path": "articles",
        "name_field": "title",
        "detail_field": "post_url",
    },
    "risk_flag": "详情同段含负责分管信息，职务只取职责动词前的原文且不删除‘任’字",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _fetch_articles(page_rule: dict) -> list[dict]:
    endpoint = str(page_rule["api"]["endpoint"])
    response = requests.get(
        endpoint,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return list(payload.get("articles", []))


def _fetch_duty(detail_url: str) -> str:
    response = requests.get(detail_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    text = next(
        (
            _clean_text(paragraph.get_text(" ", strip=True))
            for paragraph in soup.select("#zw p")
            if _clean_text(paragraph.get_text(" ", strip=True))
        ),
        "",
    )
    return re.split(r"，(?=(?:负责|分管|协助))", text, maxsplit=1)[0].strip(" ，,。")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按接口数组顺序读取姓名和详情页原始职务。"""
    del html, final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for article in _fetch_articles(page_rule):
        name = re.sub(r"\s+", "", _clean_text(str(article.get("title", ""))))
        detail_url = str(article.get("post_url") or "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not detail_url or name in seen:
            continue
        try:
            duty = _fetch_duty(detail_url)
        except (requests.RequestException, ValueError):
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
