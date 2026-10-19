from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0194",
    "page_type": "人物表格页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "list_direct",
    "leader_region_selector": ".article-content",
    "person_selector": "p strong",
    "risk_flag": "正文同时含个人简历和工作分工标题，只接受姓名开头且带职务的加粗行",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "api_config": {
        "url": "https://cg.gz.gov.cn/gkmlpt/api/all/781",
        "params": {"page": 1},
    },
}


def clean_text(value: object) -> str:
    """压缩正文排版空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def split_name_duty(value: object) -> tuple[str, str]:
    """从当前加粗行确定性分离开头姓名与其后的原始职务。"""
    line = clean_text(value)
    match = re.fullmatch(r"([\u3400-\u9fff·]{2,4})\s+(.+)", line)
    if not match:
        return "", ""
    return match.group(1), clean_text(match.group(2))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按文章正文顺序提取各人物加粗标题行。"""
    if not html:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
        config = page_rule["api_config"]
        api_response = session.get(config["url"], params=config["params"], timeout=30)
        api_response.raise_for_status()
        data = api_response.json()
        classify = data.get("classify") or {}
        articles = data.get("articles")
        if classify.get("id") != 781 or classify.get("name") != "领导分工":
            raise RuntimeError("领导分工分类接口身份异常")
        if not isinstance(articles, list) or len(articles) != 1:
            raise RuntimeError(f"领导分工分类接口文章数量异常：{len(articles or [])}")
        article_url = clean_text(articles[0].get("url"))
        if not article_url.startswith(("http://cg.gz.gov.cn/", "https://cg.gz.gov.cn/")):
            raise RuntimeError("领导分工分类接口文章链接异常")
        article_response = session.get(article_url, timeout=30)
        article_response.raise_for_status()
        article_response.encoding = "utf-8"
        html = article_response.text

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if not region:
        raise RuntimeError("未找到领导信息文章正文")

    rows: list[dict] = []
    seen_names: set[str] = set()
    for node in region.select(page_rule["person_selector"]):
        name, duty = split_name_duty(node.get_text(" ", strip=True))
        if not name or not duty or name in seen_names:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": "page_inline_guangzhou_city_management_article_strong_v2",
                "selector_summary": "region=.article-content；person=p strong；detail=none",
            }
        )

    if not rows:
        raise RuntimeError("文章正文未提取到有效人物职务行")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
