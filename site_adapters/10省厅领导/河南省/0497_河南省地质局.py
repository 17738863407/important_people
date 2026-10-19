from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0497",
    "page_type": "人物目录详情页",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": "ul#content",
    "row_selector": "ul#content a[href][title]",
    "name_selector": "ul#content a[href][title]",
    "duty_selector": "详情页p strong中的职务字段",
    "detail_link_selector": "ul#content a[href][title]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表页只提供姓名与详情链接，须逐页核验姓名归属并读取明确职务字段；当前原始HTML已包含完整结构。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", "", str(text or "")).strip()


def load_detail_html(url: str) -> tuple[str, str]:
    """在线读取人物详情页。"""
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def parse_detail(name: str, detail_html: str) -> tuple[str, str]:
    """核验姓名归属并提取详情页可见的明确职务字段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    visible_text = normalize_text(soup.get_text(" ", strip=True))
    if name not in visible_text:
        return "", ""

    for node in soup.select("p strong"):
        evidence = normalize_text(node.get_text(" ", strip=True))
        match = re.fullmatch(r"职务[:：](?P<duty>.+)", evidence)
        if match is not None:
            duty = match.group("duty").strip("，,。；; ")
            return duty, duty
    return "", ""


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录原始顺序在线解析对应详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for link in soup.select("ul#content a[href][title]"):
        name = normalize_text(str(link.get("title") or link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name):
            continue

        requested_url = urljoin(base_url, str(link.get("href") or ""))
        try:
            detail_html, detail_url = load_detail_html(requested_url)
        except requests.RequestException:
            continue
        duty, evidence = parse_detail(name, detail_html)
        if not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
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
