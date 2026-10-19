from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0584",
    "page_type": "领导分工栏目最新文章",
    "load_mode": "栏目接口转文章正文",
    "fetch_mode": "online",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".TRS_Editor p.MsoNormal",
    "risk_note": "栏目文章编号会更新，须由站内检索接口动态取得最新文章；职责文字不得并入职务证据。",
    "confidence": "high",
}


def compact_text(value: str) -> str:
    """仅移除文章排版空白，保留原始标点和文字。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """动态取得栏目最新文章，并识别编号段落中的“职务+姓名+同志”。"""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    search_url = urljoin(final_url or page_rule["url"], "/fjdzapp/search")
    response = session.post(
        search_url,
        data={
            "channelid": 229105,
            "classsql": "parentid,chnlid+=49830*modal=1",
            "sortfield": "-pubdate",
            "page": 1,
            "prepage": 10,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    articles = payload.get("data")
    if not isinstance(articles, list) or not articles:
        raise RuntimeError("领导分工栏目接口没有返回文章")
    article = articles[0]
    article_url = str(article.get("docpuburl") or article.get("chnldocurl") or "").strip()
    if article.get("chnlid") != 49830 or "/ldfg_49830/" not in article_url:
        raise RuntimeError("领导分工栏目接口返回的最新文章身份异常")
    article_response = session.get(article_url, timeout=30)
    article_response.raise_for_status()
    article_response.encoding = article_response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(article_response.text, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"^（\s*[一二三四五六七八九十]+\s*）\s*"
        r"(?P<duty>.+?(?:局长|调研员))\s*(?P<name>[\u4e00-\u9fff·]{2,4})\s*同志"
    )
    for paragraph in soup.select("p"):
        text = compact_text(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if not match:
            continue
        name = compact_text(match.group("name"))
        duty = compact_text(match.group("duty"))
        if name in seen or not duty:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("最新领导分工文章没有解析到有效人物段落")
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
