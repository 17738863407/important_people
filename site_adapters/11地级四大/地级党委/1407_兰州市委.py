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


def clean_name(value: str) -> str:
    """移除姓名节点中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(
    html: str,
    final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """限定市委领导分栏，并按目录顺序从人物详情提取完整现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".ldjs_box > .ldjs_box_left")
    if region is None:
        raise ValueError("未找到市委领导分栏 .ldjs_box > .ldjs_box_left")
    if not final_url:
        raise ValueError("在线采集结果缺少最终入口网址")

    links: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select(".shuji a[href], .fushuji a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        links.append((name, urljoin(final_url, href)))

    if not links:
        raise ValueError("市委领导分栏未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；leader=.ldjs_box > .ldjs_box_left；"
        "name=.shuji/.fushuji a[href]；duty=.ldxx .jj内完整现任句；"
        "detail=.shuji/.fushuji a[href]；collector=raw_http"
    )
    for name, detail_url in links:
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        except Exception as error:
            raise RuntimeError(f"{name}详情页采集失败：{error}") from error

        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        profile = detail_soup.select_one(".ldxx .jj")
        if profile is None:
            raise ValueError(f"{name}详情页未找到简介区域 .ldxx .jj")
        profile_text = clean_text(profile.get_text(" ", strip=True))
        current_match = re.search(r"现任[^。]*。", profile_text)
        if current_match is None:
            raise ValueError(f"{name}详情页简介未找到完整现任句")
        evidence = re.sub(r"^现任\s*", "", current_match.group(0))
        evidence = re.sub(r"[（(]\s*(?:兼|挂职|主持(?:日常)?工作)\s*[）)]", "", evidence)
        evidence = evidence.removesuffix("。").strip()
        if name not in clean_name(profile_text):
            raise ValueError(f"{name}详情页简介无法回指目录姓名")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_lanzhou_party_current_profile_v1",
                "selector_summary": selector_summary,
            }
        )

    return rows


PAGE_RULE = {
    "rule_id": "1407",
    "page_type": "人物目录详情页",
    "structure_group": "lanzhou_party_left_column_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_lanzhou_party_current_profile_v1",
    "leader_region_selector": ".ldjs_box > .ldjs_box_left",
    "name_selector": ".shuji a[href], .fushuji a[href]",
    "duty_selector": ".ldxx .jj[文本模式=现任至句号]",
    "detail_link_selector": ".shuji a[href], .fushuji a[href]",
    "detail_strategy": {"required": False, "mode": "inline_detail_fetch"},
    "risk_flag": "入口同页并列市委与市政府两组；仅抽取左侧市委分栏，姓名重复任职按首次目录位置去重",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldjs_box > .ldjs_box_left",
            "name_selector": ".shuji a[href], .fushuji a[href]",
            "duty_selector": ".ldxx .jj[文本模式=现任至句号]",
            "detail_link_selector": ".shuji a[href], .fushuji a[href]",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态目录及人物详情页稳定提供姓名、详情链接和完整现任句",
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
