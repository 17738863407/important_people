from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0339",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_city_management_list_to_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_tianjin_city_management_list_to_detail_v1",
    "leader_region_selector": "div.ldxx_left",
    "name_selector": "li a[href]",
    "duty_selector": "div.ldxx_tit .ldxx-name > p:nth-of-type(2)",
    "detail_link_selector": "li a[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "",
        "include_selectors": ["div.ldxx_left"],
        "exclude_selectors": [".dot .second-nav-box"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": "div.ldxx_left li a[href]",
        "detail_name_selector": "div.ldxx_tit .ldxx-name > p:first-of-type",
        "detail_duty_selector": "div.ldxx_tit .ldxx-name > p:nth-of-type(2)",
        "detail_content_selector": "div.ldxx_tit",
        "max_detail_links": 50,
    },
    "risk_flag": "桌面与移动目录重复；仅使用桌面左侧目录，入口等于首人详情链接时输出留空",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.ldxx_left",
            "name_selector": "li a[href]",
            "duty_selector": "div.ldxx_tit .ldxx-name > p:nth-of-type(2)",
            "detail_link_selector": "li a[href]",
            "content_scope": {
                "start_anchor": "领导信息",
                "end_anchor": "",
                "include_selectors": ["div.ldxx_left"],
                "exclude_selectors": [".dot .second-nav-box"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "入口左侧目录和人物详情标题块均为稳定静态HTML",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理排版空白，不改变职务文字。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def _clean_name(value: str) -> str:
    """移除姓名中的视觉排版空格。"""
    return re.sub(r"\s+", "", value or "")


def _parse_detail(session: requests.Session, detail_url: str, expected_name: str) -> str:
    """在线读取人物详情标题块中的职务，并核对姓名归属。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    parts = soup.select("div.ldxx_tit .ldxx-name > p")
    if len(parts) < 2:
        raise RuntimeError(f"详情页缺少姓名或职务标题：{detail_url}")
    actual_name = _clean_name(parts[0].get_text(" ", strip=True))
    if actual_name != expected_name:
        raise RuntimeError(f"详情页姓名不匹配：期望{expected_name}，实际{actual_name}")
    duty = _clean_text(parts[1].get_text(" ", strip=True)).rstrip("。 ")
    if not duty:
        raise RuntimeError(f"详情页职务为空：{detail_url}")
    return duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按左侧人物目录顺序逐一在线读取详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    source_host = urlparse(source_url).netloc.lower()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": source_url})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select("div.ldxx_left li a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue

        candidate = urljoin(final_url or source_url, str(link.get("href") or "").strip())
        parsed = urlparse(candidate)
        real_person_page = bool(re.fullmatch(r"/zwgk_57/ldxx/\d{6}/t\d{8}_\d+\.html", parsed.path))
        if parsed.netloc.lower() != source_host or not real_person_page:
            continue

        duty = _parse_detail(session, candidate, name)
        output_detail_url = "" if candidate.rstrip("/") == source_url.rstrip("/") else candidate
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": output_detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_city_management_list_to_detail_v1",
                "selector_summary": "桌面左侧目录原序；详情页ldxx_tit姓名/职务标题",
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
