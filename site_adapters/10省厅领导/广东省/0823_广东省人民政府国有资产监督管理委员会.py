from __future__ import annotations

import re
import sys
from pathlib import Path

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0823",
    "page_type": "人物列表完整页",
    "structure_group": "gd_gkmlpt_api_abstract_current_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_direct",
    "collector": "raw_http_api",
    "parser": "builtin_parse_page",
    "leader_region_selector": "API articles[]",
    "name_selector": "articles[].title",
    "duty_selector": "articles[].abstract现任句",
    "detail_link_selector": "articles[].post_url",
    "detail_strategy": {"required": False, "mode": "none"},
    "api": {
        "enabled": True,
        "endpoint": "https://gzw.gd.gov.cn/gkmlpt/api/all/1326?page=1&sid=195",
        "method": "GET",
        "data_path": "articles",
        "name_field": "title",
        "evidence_field": "abstract",
        "detail_field": "post_url",
    },
    "risk_flag": "接口含简介与联系方式，仅使用abstract内完整现任句",
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按接口数组顺序提取姓名、完整现任句和人物详情链接。"""
    del html, final_url
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for article in _fetch_articles(page_rule):
        name = re.sub(r"\s+", "", _clean_text(str(article.get("title", ""))))
        abstract = _clean_text(str(article.get("abstract", "")))
        current_match = re.search(r"现任[^。]*。", abstract)
        detail_url = str(article.get("post_url") or "")
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or current_match is None
            or not detail_url
            or name in seen
        ):
            continue
        evidence = current_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。").strip()
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
