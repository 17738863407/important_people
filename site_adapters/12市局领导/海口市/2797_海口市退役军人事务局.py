from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2797",
    "page_type": "人物目录详情页",
    "structure_group": "haikou_veterans_iframe_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "haikou_veterans_iframe_profiles_v1",
    "leader_region_selector": "iframe[src*='/ldxx/ldxx.shtml']",
    "name_selector": "iframe人物链接内em",
    "duty_selector": "#tyjr_content当前人物简介或姓名后职务段",
    "detail_link_selector": "iframe人物链接a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "iframe_list_to_detail",
        "detail_name_selector": "meta[name='ArticleTitle']",
        "detail_content_selector": "#tyjr_content",
        "max_detail_links": 50,
    },
    "risk_flag": "部分详情无现任句，回退到当前人物姓名段后的明确职务段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: str) -> str:
    """压缩网页排版空白，保留原文标点。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", value or "").strip()


def valid_detail_url(href: str, iframe_url: str) -> str:
    """校验退役军人事务局站内人物详情页路径。"""
    detail_url = urljoin(iframe_url, href)
    frame = urlparse(iframe_url)
    detail = urlparse(detail_url)
    if detail.netloc != frame.netloc:
        return ""
    if not re.search(r"/ldxx/\d{6}/t\d+\.shtml(?:$|[?#])", detail_url):
        return ""
    return detail_url


def extract_detail(name: str, detail_soup: BeautifulSoup) -> tuple[str, str]:
    """只在当前人物正文中提取现任句或明确职务段。"""
    content = detail_soup.select_one("#tyjr_content")
    if content is None:
        raise ValueError(f"详情缺少人物正文：{name}")
    text = compact_text(content.get_text(" ", strip=True))
    current = re.search(r"(?P<evidence>现任(?P<duty>[^。]+)。)", text)
    if current:
        return current.group("duty"), current.group("duty")

    paragraphs = content.find_all("p")
    name_index = next(
        (index for index, node in enumerate(paragraphs) if compact_text(node.get_text(" ", strip=True)) == name),
        -1,
    )
    if name_index < 0:
        raise ValueError(f"详情正文未定位到姓名段：{name}")
    for node in paragraphs[name_index + 1 :]:
        value = compact_text(node.get_text(" ", strip=True))
        if not value:
            continue
        if value.startswith("分工"):
            break
        return value, value
    raise ValueError(f"详情正文未发现明确职务字段：{name}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态抓取领导iframe，再按目录顺序逐页解析人物。"""
    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.select_one("iframe[src*='/ldxx/ldxx.shtml']")
    if iframe is None or not iframe.get("src"):
        raise ValueError("入口页未发现领导信息iframe")
    iframe_url = urljoin(final_url, iframe.get("src", ""))

    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        frame_response = session.get(iframe_url, timeout=30)
        frame_response.raise_for_status()
        frame_response.encoding = frame_response.apparent_encoding or frame_response.encoding
        frame_soup = BeautifulSoup(frame_response.text, "html.parser")
        candidates: list[tuple[str, str]] = []
        for link in frame_soup.select("a[href]:has(em)"):
            name_node = link.select_one("em")
            name = compact_text(name_node.get_text(" ", strip=True)) if name_node else ""
            detail_url = valid_detail_url(link.get("href", ""), frame_response.url)
            if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) and detail_url:
                candidates.append((name, detail_url))
        if not candidates:
            raise ValueError("领导iframe未发现有效人物详情链接")

        records: list[dict[str, str]] = []
        for name, detail_url in candidates:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            detail_soup = BeautifulSoup(response.text, "html.parser")
            title = detail_soup.select_one("meta[name='ArticleTitle']")
            if title is None or compact_text(title.get("content", "")) != name:
                raise ValueError(f"详情标题姓名不一致：{name}")
            duty, evidence = extract_detail(name, detail_soup)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": evidence,
                    "detail_url": response.url,
                    "selector_summary": "入口iframe动态发现→em姓名链接→详情标题校验→#tyjr_content",
                }
            )
    return records


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
