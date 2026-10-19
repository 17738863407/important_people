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


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按领导介绍列表原始顺序抓取详情，并提取完整“现任……”原句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    directory = soup.select_one("div.introduce_list")
    if directory is None:
        raise ValueError("未找到领导介绍区域 div.introduce_list")

    base_url = final_url or str(page_rule.get("url", ""))
    links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in directory.select("a[href]"):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        links.append((name, detail_url))

    if not links:
        raise ValueError("领导介绍区域未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；leader=div.introduce_list；name=a[href]；"
        "duty=detail .art_con内完整现任句；detail=div.introduce_list a[href]；collector=raw_http"
    )
    for name, detail_url in links:
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        except Exception as error:
            raise RuntimeError(f"{name}详情页采集失败：{error}") from error

        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        article = detail_soup.select_one(".art_con")
        if article is None:
            raise ValueError(f"{name}详情页未找到 .art_con")
        article_text = clean_text(article.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", article_text)
        if current_match is None:
            raise ValueError(f"{name}详情页 .art_con 未找到完整“现任……”句")
        evidence = current_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。").strip()
        if not duty:
            raise ValueError(f"{name}详情页现任职务内容为空")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_dalian_wlj_current_profile_v1",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2913",
    "page_type": "人物列表完整页",
    "structure_group": "dalian_wlj_introduce_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_dalian_wlj_current_profile_v1",
    "leader_region_selector": "div.introduce_list",
    "name_selector": "a[href]",
    "duty_selector": ".art_con内完整现任句",
    "detail_link_selector": "div.introduce_list a[href]",
    "detail_strategy": {"required": False, "mode": "inline_detail_fetch"},
    "risk_flag": "入口源码的领导区域由页面脚本切换显示；已核验浏览器渲染后目标区域可见且移除hide类",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.introduce_list",
            "name_selector": "a[href]",
            "duty_selector": ".art_con",
            "detail_link_selector": "div.introduce_list a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "领导目录和人物详情均在公开静态HTML中直接提供",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
