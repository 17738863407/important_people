from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1292",
    "page_type": "人物列表完整页",
    "structure_group": "tianjin_edu_leader_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_edu_leader_details_v1",
    "leader_region_selector": "p.list-content",
    "name_selector": "p.list-content",
    "duty_selector": "详情.content中姓名段后、工作分工前的首个非空p",
    "detail_link_selector": "p.list-content父级a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["p.list-content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "p.list-content父级a[href]",
        "detail_name_selector": ".content p",
        "detail_duty_selector": ".content中姓名后首个非空p",
        "detail_content_selector": ".content",
        "max_detail_links": 50,
    },
    "risk_flag": "详情页姓名重复两次，职务位于重复姓名后和工作分工标题前；必须排除后续长段职责，不使用职务关键词过滤",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "p.list-content",
            "name_selector": "p.list-content",
            "duty_selector": "详情.content中姓名段后、工作分工前的首个非空p",
            "detail_link_selector": "p.list-content父级a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "工作分工",
                "include_selectors": [".content"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML列表提供人物链接，详情正文通过稳定段落顺序提供姓名、职务和分工边界",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理零宽字符、全角空格和排版空白。"""
    text = (value or "").replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    """清理姓名中的网页排版空格。"""
    return re.sub(r"\s+", "", _clean_text(value))


def _fetch_detail(url: str) -> tuple[str, str]:
    """在线获取人物详情页HTML及最终地址。"""
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_detail_duty(html: str, expected_name: str) -> str:
    """读取重复姓名之后、工作分工之前的首个非空职务段。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".content")
    if scope is None:
        return ""

    for paragraph in scope.select("p"):
        line = _clean_text(paragraph.get_text(" ", strip=True))
        if not line:
            continue
        compact = _clean_name(line)
        if compact == expected_name:
            continue
        if compact == "工作分工":
            break
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", line)
        return duty.strip("：:，。 ")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按列表DOM顺序在线解析人物详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for name_node in soup.select("p.list-content"):
        link = name_node.find_parent("a")
        name = _clean_name(name_node.get_text(" ", strip=True))
        if not link or not link.get("href") or not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue

        candidate_url = urljoin(base_url, str(link.get("href", "")))
        detail_html, detail_url = _fetch_detail(candidate_url)
        duty = _extract_detail_duty(detail_html, name)
        if not duty:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_edu_leader_details_v1",
                "selector_summary": "p.list-content人物目录；详情.content重复姓名后、工作分工前首个p",
            }
        )

    return rows


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
