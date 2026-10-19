from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2244",
    "page_type": "人物目录详情页",
    "structure_group": "gxzf_leader_directory_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "page_local_parse_page",
    "collector": "static_http",
    "parser": "page_local_parse_page",
    "leader_region_selector": "#morelist .more-list",
    "name_selector": "#morelist .more-list a[href]",
    "duty_selector": ".trs_editor_view, #ldjj-wrap 内当前人物的完整现任句",
    "detail_link_selector": "#morelist .more-list a[href]",
    "risk_flag": "首位李泽使用同站领导地图详情页，其他人物使用t数字详情页，不能按文件名形态排除",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    """压缩网页排版空白，保留可回指的正文文字。"""
    compact = re.sub(r"\s+", " ", value).strip()
    compact = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", compact)
    return re.sub(r"(?<=[，。；：])\s+(?=[\u3400-\u9fff])", "", compact)


def _request_html(session: requests.Session, url: str) -> tuple[str, str]:
    """请求同站静态页面并返回正文与最终网址。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _find_exact_link(soup: BeautifulSoup, text: str, base_url: str) -> str:
    """按官网栏目标题定位下一层链接，避免依赖易变的层级样式。"""
    for anchor in soup.find_all("a", href=True):
        if _clean_text(anchor.get_text(" ", strip=True)) == text:
            return urljoin(base_url, anchor["href"])
    raise ValueError(f"未找到官网栏目链接：{text}")


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """沿官网栏目导航取得领导目录，并从各人物详情页提取现任句。"""
    del page_rule
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    entry_soup = BeautifulSoup(html, "html.parser")
    overview_url = _find_exact_link(entry_soup, "概况信息", final_url)

    overview_html, overview_final_url = _request_html(session, overview_url)
    overview_soup = BeautifulSoup(overview_html, "html.parser")
    functions_url = _find_exact_link(overview_soup, "机构职能", overview_final_url)

    functions_html, functions_final_url = _request_html(session, functions_url)
    functions_soup = BeautifulSoup(functions_html, "html.parser")
    directory_url = _find_exact_link(functions_soup, "领导简介", functions_final_url)

    directory_html, directory_final_url = _request_html(session, directory_url)
    directory_soup = BeautifulSoup(directory_html, "html.parser")
    directory_host = urlparse(directory_final_url).netloc.lower()

    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in directory_soup.select("#morelist .more-list a[href]"):
        name = _clean_text(anchor.get_text(" ", strip=True))
        detail_url = urljoin(directory_final_url, anchor["href"])
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            continue
        if urlparse(detail_url).netloc.lower() != directory_host:
            continue
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))

    if not candidates:
        raise ValueError("领导简介目录未发现可核验的独立人物链接")

    rows: list[dict[str, str]] = []
    for name, detail_url in candidates:
        detail_html, detail_final_url = _request_html(session, detail_url)
        detail_soup = BeautifulSoup(detail_html, "html.parser")
        content = detail_soup.select_one(".trs_editor_view, #ldjj-wrap")
        if content is None:
            raise ValueError(f"人物详情页缺少正文容器：{detail_final_url}")
        content_text = _clean_text(content.get_text(" ", strip=True))
        if name not in content_text:
            raise ValueError(f"人物姓名无法回指详情正文：{detail_final_url}")
        current_match = re.search(r"现任[^。]*。", content_text)
        if current_match is None:
            raise ValueError(f"人物详情页缺少完整现任句：{detail_final_url}")
        rows.append(
            {
                "name": name,
                "duty": current_match.group(0).removeprefix("现任").removesuffix("。").replace("（兼）", "").replace("(兼)", ""),
                "detail_url": detail_final_url,
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
