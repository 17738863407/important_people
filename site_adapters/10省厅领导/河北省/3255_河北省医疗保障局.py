from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3255",
    "page_type": "人物目录详情页",
    "load_mode": "图片承载",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".news-list",
    "row_selector": ".news-list a.news-item[href]",
    "name_selector": ".news-list a.news-item .title",
    "duty_selector": "详情正文访问次数后、姓名前的职务文本",
    "detail_link_selector": ".news-list a.news-item[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表仅提供姓名和详情链接，职务须从对应详情正文中动态提取；页面画像名称虽为图片承载，当前权威数据为HTML文本。",
}


def normalize_text(text: str) -> str:
    """确定性清理HTML排版空白。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ")).strip()


def load_detail_html(url: str) -> tuple[str, str]:
    """在线读取人物详情页，不创建或依赖本地快照。"""
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def parse_detail_duty(name: str, detail_html: str) -> str:
    """从详情正文“访问次数：职务 姓名：分工”结构提取原始职务。"""
    text = normalize_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
    match = re.search(
        r"访问次数：\s*(?P<duty>局\s*党组[^：]{1,70}?)\s*"
        + re.escape(name)
        + r"\s*：",
        text,
    )
    if match is None:
        return ""
    return normalize_text(match.group("duty")).replace("局 党组", "局党组")


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表顺序访问对应详情页并恢复原始顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for link in soup.select(".news-list a.news-item[href]"):
        title = link.select_one(".title")
        name = normalize_text(title.get_text(" ", strip=True) if title else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue

        requested_url = urljoin(base_url, str(link.get("href") or ""))
        try:
            detail_html, detail_url = load_detail_html(requested_url)
        except requests.RequestException:
            continue
        duty = parse_detail_duty(name, detail_html)
        if not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
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
