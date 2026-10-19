from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0546",
    "page_type": "人物目录详情页",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".zfxxgk_zdgkc > ul",
    "row_selector": ".zfxxgk_zdgkc > ul > li",
    "name_selector": ".zfxxgk_zdgkc > ul > li > a[title]",
    "duty_selector": "详情页.conBox人物简介首句姓名前文本",
    "detail_link_selector": ".zfxxgk_zdgkc > ul > li > a[href][title]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表仅提供姓名与详情链接，详情简介将职务、姓名和人口学信息连续展示；当前原始HTML已包含完整结构。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", "", str(text or "")).strip()


def load_detail_html(url: str) -> tuple[str, str]:
    """在线读取人物详情页。"""
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url.replace(":443/", "/")


def parse_detail(name: str, detail_html: str) -> tuple[str, str]:
    """从当前人物简介首句提取姓名前的原始职务。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for paragraph in soup.select(".conBox p"):
        profile_text = normalize_text(paragraph.get_text(" ", strip=True))
        match = re.match(
            r"^(?P<duty>.+?)" + re.escape(name) + r"[，,](?:男|女)[，,]",
            profile_text,
        )
        if match is None:
            continue
        duty = match.group("duty").strip("：:，,。；; ")
        if duty:
            return duty, duty
    return "", ""


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表顺序在线解析对应详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for link in soup.select(".zfxxgk_zdgkc > ul > li > a[href][title]"):
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
