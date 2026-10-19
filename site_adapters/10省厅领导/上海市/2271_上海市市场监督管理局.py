from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2271",
    "page_type": "人物列表完整页",
    "load_mode": "iframe嵌入",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "#news_frame",
    "risk_note": "入口脚本按changeId设置iframe地址，人物数据位于iframe表格且源码含注释旧名单。",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """压缩表格字段中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def resolve_iframe_url(html: str, final_url: str) -> str:
    """根据入口changeId与页面脚本动态确定当前iframe地址。"""
    change_id = parse_qs(urlsplit(final_url).query).get("changeId", [""])[0]
    if not re.fullmatch(r"\d+", change_id):
        raise RuntimeError("入口地址缺少有效changeId")
    iframe_path = f"/{change_id}/"
    pattern = rf'document\.getElementById\(["\']news_frame["\']\)\.src=["\']{re.escape(iframe_path)}["\']'
    if not re.search(pattern, html):
        raise RuntimeError(f"页面脚本未声明目标iframe：{iframe_path}")
    return urljoin(final_url, iframe_path)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """在线读取当前iframe并按现任领导表格行顺序提取字段。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    iframe_url = resolve_iframe_url(html, final_url)
    result = fetch_html_with_strategy(iframe_url, "raw_http")
    soup = BeautifulSoup(result.html, "html.parser")
    rows: list[dict] = []

    for table_row in soup.select("table tr"):
        cells = table_row.select("th, td")
        if len(cells) < 2:
            continue
        link = cells[0].select_one("a[href]")
        if link is None:
            continue
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        evidence = clean_text(cells[1].get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not evidence:
            continue
        rows.append(
            {
                "name": name,
                "duty": "",
                "evidence": evidence,
                "detail_url": urljoin(result.final_url, link.get("href", "").strip()),
            }
        )

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
