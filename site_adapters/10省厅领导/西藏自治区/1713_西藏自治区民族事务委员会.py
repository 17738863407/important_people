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
    "rule_id": "1713",
    "page_type": "人物目录详情页",
    "structure_group": "xizang_ethnic_affairs_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_xizang_ethnic_affairs_directory_details_v1",
    "leader_region_selector": ".g-main.bgBox",
    "name_selector": ".g-main.bgBox a.e[href]",
    "duty_selector": "详情.nxz-art-cont .view首个非空文本段",
    "detail_link_selector": ".g-main.bgBox a.e[href]",
    "content_scope": {
        "start_anchor": "领导简介",
        "end_anchor": "",
        "include_selectors": [".g-main.bgBox a.e[href]", ".nxz-art-cont .view"],
        "exclude_selectors": ["发布时间", "主持", "分管", "相关新闻", "友情链接"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "directory_details",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".g-main.bgBox a.e[href]",
        "detail_name_selector": ".nxz-art-head .title",
        "detail_duty_selector": ".nxz-art-cont .view首个非空文本段",
        "detail_content_selector": ".nxz-art-cont .view",
        "max_detail_links": 50,
    },
    "risk_flag": "详情正文首个非空文本段为职务，下一段为主持或分管；头像图片不是名单和人物详情链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".g-main.bgBox",
            "name_selector": "a.e[href]",
            "duty_selector": "详情.nxz-art-cont .view p首个非空文本",
            "detail_link_selector": "a.e[href]",
            "content_scope": {
                "start_anchor": "详情正文首个非空文本段",
                "end_anchor": "详情正文第二个非空文本段",
                "include_selectors": [".nxz-art-cont .view p"],
                "exclude_selectors": ["头像图片", "主持", "分管"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML目录与详情正文可直接稳定提供姓名、职务和人物链接",
        },
    },
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u2002", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    return re.sub(r"\s+", "", _clean_text(value))


def _clean_evidence(value: str) -> str:
    """移除固定标签和纯句末标点，保留原始职务内容。"""
    text = re.sub(r"^(?:职务|现任职务|现任)[：:]?", "", _clean_text(value))
    return text.rstrip("。")


def _fetch_detail(url: str) -> tuple[str, str]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def _extract_detail(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".nxz-art-head .title")
    if title is None or _clean_name(title.get_text(" ", strip=True)) != expected_name:
        return ""
    for paragraph in soup.select(".nxz-art-cont .view p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if text:
            return text
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口目录DOM顺序在线读取详情正文首个非空职务段。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".g-main.bgBox a.e[href]"):
        name = _clean_name(str(link.get("title", "")) or link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name) or name in seen:
            continue
        requested_url = urljoin(base_url, str(link.get("href", "")))
        detail_html, _final_detail_url = _fetch_detail(requested_url)
        duty = _clean_evidence(_extract_detail(detail_html, name))
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": requested_url,
                "evidence": duty,
                "parser": "custom_xizang_ethnic_affairs_directory_details_v1",
                "selector_summary": ".g-main.bgBox a.e目录；详情.nxz-art-cont .view首个非空文本段",
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
