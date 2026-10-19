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
    """按领导卡片原始顺序抓取详情，并提取基本信息中的完整现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    directory = soup.select_one(".gkpd-l-nr")
    if directory is None:
        raise ValueError("未找到领导信息区域 .gkpd-l-nr")

    base_url = final_url or str(page_rule.get("url", ""))
    links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in directory.select("a[href]"):
        href = str(link.get("href") or "").strip()
        if "ldxx" not in href:
            continue
        name_node = link.select_one("span.ldmc")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_url = urljoin(base_url, href)
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        links.append((name, detail_url))

    if not links:
        raise ValueError("领导信息区域未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；leader=.gkpd-l-nr；name=span.ldmc；"
        "duty=detail p.detail内完整现任句；detail=.gkpd-l-nr a[href包含ldxx]；collector=raw_http"
    )
    for name, detail_url in links:
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        except Exception as error:
            raise RuntimeError(f"{name}详情页采集失败：{error}") from error

        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        profile = detail_soup.select_one("p.detail")
        if profile is None:
            raise ValueError(f"{name}详情页未找到 p.detail")
        profile_text = clean_text(profile.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", profile_text)
        if current_match is None:
            raise ValueError(f"{name}详情页 p.detail 未找到完整“现任……”句")
        duty = current_match.group(0).removeprefix("现任").removesuffix("。").strip()
        evidence = duty
        if not duty:
            raise ValueError(f"{name}详情页现任职务内容为空")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_haikou_hrss_current_profile_v1",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "2200",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_hrss_leader_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_haikou_hrss_current_profile_v1",
    "leader_region_selector": ".gkpd-l-nr",
    "name_selector": "span.ldmc",
    "duty_selector": "p.detail内完整现任句",
    "detail_link_selector": ".gkpd-l-nr a[href*='ldxx']",
    "detail_strategy": {"required": False, "mode": "inline_detail_fetch"},
    "risk_flag": "新旧详情页编辑器外层类不同，统一限定当前人物基本信息 p.detail，排除其后的分工区域",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".gkpd-l-nr",
            "name_selector": "span.ldmc",
            "duty_selector": "p.detail",
            "detail_link_selector": ".gkpd-l-nr a[href*='ldxx']",
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
