from __future__ import annotations

import json
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
    "rule_id": "4323",
    "page_type": "article_photo_groups",
    "load_mode": "http",
    "parser": "custom",
    "risk": "入口页的 articleList 动态指向领导之窗正文，正文表格的锚文本同时给出职务和姓名。",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    """从入口页当前 articleList 找到领导正文，再按正文表格阅读顺序提取。"""
    from bs4 import BeautifulSoup
    import requests

    article_match = re.search(r"var\s+articleList\s*=\s*(\[.*?\]);", html, re.S)
    if not article_match:
        return []
    articles = json.loads(article_match.group(1))
    if not articles:
        return []
    urls = articles[0].get("urls", "{}")
    content_path = json.loads(urls).get("pc") if isinstance(urls, str) else urls.get("pc")
    if not content_path:
        return []
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        urljoin(final_url, content_path),
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select("#zoomcon table a[href]"):
        text = re.sub(r"[\s\u3000]+", "", link.get_text(" ", strip=True))
        match = re.fullmatch(r"(主席|副主席|秘书长)([\u4e00-\u9fff]{2,4})", text)
        if match:
            rows.append(
                {
                    "name": match.group(2),
                    "duty": match.group(1),
                    "detail_url": urljoin(response.url, link["href"]),
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
