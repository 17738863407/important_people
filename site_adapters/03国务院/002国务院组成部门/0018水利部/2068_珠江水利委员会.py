from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2068",
    "page_type": "人物目录详情页",
    "structure_group": "pearlwater_chrome_leader_profiles_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "page_local_parse_page",
    "collector": "chrome_cdp",
    "parser": "page_local_parse_page",
    "leader_region_selector": ".list_sidebar > ul > li.open > ul",
    "name_selector": ":scope > li > a[href]",
    "duty_selector": ".TRS_Editor 内当前人物的完整现任句",
    "detail_link_selector": ".intro h1 > a[href]",
    "risk_flag": "HTTP 412且Playwright仅39字节，需Chrome逐个渲染；必须排除简历前缀、工作分工和工作活动",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    """确定性压缩网页排版空白。"""
    return re.sub(r"\s+", " ", value).strip()


def _clean_name(value: str) -> str:
    """姓名仅移除页面排版空白。"""
    return re.sub(r"\s+", "", value)


def _parse_profile(html: str, page_url: str, expected_name: str) -> dict[str, str]:
    """从已定位的当前人物页提取现任句及一一对应简介文章。"""
    soup = BeautifulSoup(html, "html.parser")
    heading_link = soup.select_one("article .intro h1 > a[href]")
    content = soup.select_one("article .TRS_Editor")
    if heading_link is None or content is None:
        raise ValueError(f"人物页缺少简介标题或正文容器：{page_url}")

    heading_text = _clean_name(heading_link.get_text(" ", strip=True))
    if not heading_text.startswith(expected_name):
        raise ValueError(f"侧栏姓名与人物页标题不一致：{page_url}")
    content_text = _clean_text(content.get_text(" ", strip=True))
    current_match = re.search(r"现任[^。]*。", content_text)
    if current_match is None:
        raise ValueError(f"当前人物正文缺少完整现任句：{page_url}")

    detail_url = urljoin(page_url, heading_link["href"])
    detail_path = urlparse(detail_url).path
    page_path = urlparse(page_url).path.rstrip("/") + "/"
    if not detail_path.startswith(page_path) or not detail_path.endswith(".html"):
        raise ValueError(f"简介文章链接不属于当前人物目录：{detail_url}")
    evidence = re.sub(r"^现任", "", current_match.group(0)).rstrip("。")
    return {
        "name": expected_name,
        "duty": evidence,
        "detail_url": detail_url,
    }


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按领导侧栏原序渲染各人物页，保留当前人物块内完整现任句。"""
    del page_rule
    entry_soup = BeautifulSoup(html, "html.parser")
    directory = entry_soup.select_one(".list_sidebar > ul > li.open > ul")
    if directory is None:
        raise ValueError("领导简介页缺少当前展开的领导侧栏")

    candidates: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    seen_pages: set[str] = set()
    for anchor in directory.select(":scope > li > a[href]"):
        name = _clean_name(anchor.get_text(" ", strip=True))
        page_url = urljoin(final_url, anchor["href"])
        page_path = urlparse(page_url).path
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            continue
        if not re.fullmatch(r"/jgzzcs/ldjjcs/[^/]+/", page_path):
            continue
        if name in seen_names or page_url in seen_pages:
            raise ValueError(f"领导侧栏存在重复姓名或页面：{name}")
        seen_names.add(name)
        seen_pages.add(page_url)
        candidates.append((name, page_url))
    if not candidates:
        raise ValueError("领导侧栏未发现可核验的人物分类链接")

    from crawler_core.fetcher import fetch_by_chrome_debug

    rows: list[dict[str, str]] = []
    seen_details: set[str] = set()
    current_path = urlparse(final_url).path.rstrip("/") + "/"
    for name, page_url in candidates:
        candidate_path = urlparse(page_url).path.rstrip("/") + "/"
        if candidate_path == current_path:
            profile_html = html
            profile_url = final_url
        else:
            result = fetch_by_chrome_debug(page_url, timeout=45)
            profile_html = result.html
            profile_url = result.final_url
        row = _parse_profile(profile_html, profile_url, name)
        if row["detail_url"] in seen_details:
            raise ValueError(f"多名人物复用了同一简介文章：{row['detail_url']}")
        seen_details.add(row["detail_url"])
        rows.append(row)
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
