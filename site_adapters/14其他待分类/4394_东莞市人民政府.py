from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4394",
    "page_type": "government_leader_detail_directory",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "入口为副市长详情页；只读取左侧市政府领导目录中的现行人物，并逐页取得明确职务字段。",
    "confidence": "high",
}


def _https_url(url: str) -> str:
    """将官网目录中的同域 HTTP 链接规范为 HTTPS。"""
    parts = urlsplit(url)
    return urlunsplit(("https", parts.netloc, parts.path, parts.query, parts.fragment))


def _request_text(url: str) -> str:
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(
        _https_url(url),
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=25,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按市政府领导目录顺序读取各人物详情页的姓名和职务字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    directory = soup.select_one("#nav3 .lf_lb")
    if directory is None:
        return []
    rows: list[dict[str, str]] = []
    normalized_entry = _https_url(final_url)
    for link in directory.select("li.ltp a[href]"):
        detail_url = _https_url(urljoin(final_url, link["href"]))
        detail = BeautifulSoup(_request_text(detail_url), "html.parser")
        name_node = detail.select_one("#rightFrame #bt, #ld_name")
        duty_node = detail.select_one("#rightFrame #zw")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = duty_node.get_text(" ", strip=True) if duty_node else ""
        if name and duty:
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "detail_url": "" if detail_url == normalized_entry else detail_url,
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
