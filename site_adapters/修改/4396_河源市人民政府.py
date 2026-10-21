from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4396",
    "page_type": "政府领导详情目录",
    "structure_group": "heyuan_leader_directory_details_v1",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_heyuan_leader_details_v1",
    "leader_region_selector": ".box-ld",
    "detail_strategy": {"required": True, "mode": "directory_to_detail"},
    "risk_flag": "入口可能跳转移动版；从领导之窗栏目取得当前顺序，详情页只抽取现任句，不取分工。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "leader_directory_to_current_sentence",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按领导之窗栏目顺序抓取详情页中的当前职务句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    directory_anchor = next(
        (
            anchor
            for anchor in soup.find_all("a", href=True)
            if "".join(anchor.get_text(" ", strip=True).split()) == "领导之窗"
            and "/zwgk/ldzc/" in str(anchor.get("href") or "")
        ),
        None,
    )
    if directory_anchor is None:
        raise RuntimeError("入口详情页未提供领导之窗栏目链接")
    directory_url = urljoin(final_url, str(directory_anchor["href"]))
    directory_result = fetch_html_with_strategy(
        directory_url,
        strategy="requests",
        timeout=30,
    )
    directory = BeautifulSoup(directory_result.html, "html.parser")
    leader_links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in directory.find_all("a", href=True):
        href = urljoin(directory_result.final_url, str(anchor["href"]))
        name = "".join(str(anchor.get("title") or anchor.get_text(" ", strip=True)).split())
        if "/zwgk/ldzc/content/" not in href or href in seen_urls:
            continue
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            continue
        seen_urls.add(href)
        leader_links.append((name, href))
    if not leader_links:
        raise RuntimeError("领导之窗栏目未发现当前人物详情链接")

    rows: list[dict[str, str]] = []
    for expected_name, detail_url in leader_links:
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="requests",
            timeout=30,
        )
        detail = BeautifulSoup(detail_result.html, "html.parser")
        root = detail.select_one(".box-ld")
        if root is None:
            raise RuntimeError(f"人物详情页缺少 .box-ld：{detail_url}")
        page_name_node = detail.select_one('meta[name="ArticleTitle"]')
        page_name = str(page_name_node.get("content") or "").strip() if page_name_node else ""
        if page_name and page_name != expected_name:
            raise RuntimeError(f"人物详情标题不一致：{expected_name} -> {page_name}")
        current_sentence = next(
            (
                " ".join(paragraph.get_text(" ", strip=True).split())
                for paragraph in root.select("p")
                if " ".join(paragraph.get_text(" ", strip=True).split()).startswith("现任")
            ),
            "",
        )
        if not current_sentence:
            raise RuntimeError(f"人物详情页缺少现任职务句：{detail_url}")
        duty = re.sub(r"\s+", "", current_sentence.removeprefix("现任")).rstrip("。；;")
        rows.append({"name": expected_name, "duty": duty, "detail_url": detail_url})
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
