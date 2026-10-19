from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PAGE_RULE = {
    "rule_id": "2994",
    "page_type": "人物目录详情页",
    "structure_group": "jilin_health_visible_leader_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "page_local_parse_page",
    "collector": "static_http",
    "parser": "page_local_parse_page",
    "leader_region_selector": ".tldpic .ldzp",
    "name_selector": ":scope > p > a[href]",
    "duty_selector": ".xiqingx > p:nth-of-type(2)",
    "detail_link_selector": ".xiqingx > p:first-of-type a[href]",
    "risk_flag": "需排除display:none旧卡片，并从人物分类页取得原始职务和独立简介链接",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    """确定性清理页面排版空白。"""
    return re.sub(r"\s+", " ", value).strip()


def _clean_name(value: str) -> str:
    """清除姓名中的普通空白及页面使用的韩文填充符。"""
    return re.sub(r"[\s\u3164]+", "", value)


def _is_hidden(node: Tag) -> bool:
    """检查节点及祖先的显式隐藏状态。"""
    current: Tag | None = node
    while current is not None:
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        classes = {str(item).lower() for item in current.get("class", [])}
        if current.has_attr("hidden") or current.get("aria-hidden") == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style:
            return True
        if classes.intersection({"hidden", "hide", "none"}):
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def _request_soup(session: requests.Session, url: str) -> tuple[BeautifulSoup, str]:
    """在线请求UTF-8静态页面。"""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return BeautifulSoup(response.text, "html.parser"), response.url


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按可见卡片原序进入人物分类页，提取职务并核验独立简介页。"""
    del page_rule
    entry_soup = BeautifulSoup(html, "html.parser")
    cards = [card for card in entry_soup.select(".tldpic .ldzp") if not _is_hidden(card)]
    if not cards:
        raise ValueError("委领导页面未发现可见人物卡片")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_details: set[str] = set()

    for card in cards:
        card_link = card.select_one(":scope > p > a[href]")
        if card_link is None:
            raise ValueError("可见人物卡片缺少姓名链接")
        name = _clean_name(card_link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            raise ValueError(f"人物卡片姓名结构异常：{name}")
        if name in seen_names:
            raise ValueError(f"可见人物卡片出现重复姓名：{name}")

        category_url = urljoin(final_url, card_link["href"])
        category_soup, category_final_url = _request_soup(session, category_url)
        profile = category_soup.select_one(".xiqingx")
        if profile is None:
            raise ValueError(f"人物分类页缺少姓名职务区域：{category_final_url}")
        paragraphs = profile.find_all("p", recursive=False)
        if len(paragraphs) < 2:
            raise ValueError(f"人物分类页姓名职务字段不完整：{category_final_url}")
        profile_name = _clean_name(paragraphs[0].get_text(" ", strip=True))
        duty = _clean_text(paragraphs[1].get_text(" ", strip=True)).replace("（兼）", "").replace("(兼)", "")
        if profile_name != name or not duty:
            raise ValueError(f"人物卡片与分类页姓名职务不一致：{category_final_url}")

        detail_anchor = paragraphs[0].find("a", href=True)
        if detail_anchor is None:
            raise ValueError(f"人物分类页缺少独立简介链接：{category_final_url}")
        detail_url = urljoin(category_final_url, detail_anchor["href"])
        detail_soup, detail_final_url = _request_soup(session, detail_url)
        detail_title = _clean_name(detail_soup.title.get_text(" ", strip=True)) if detail_soup.title else ""
        detail_text = _clean_name(detail_soup.get_text(" ", strip=True))
        if name not in detail_title and name not in detail_text:
            raise ValueError(f"独立简介页无法回指人物姓名：{detail_final_url}")
        if detail_final_url in seen_details:
            raise ValueError(f"多名人物复用了同一详情页：{detail_final_url}")

        seen_names.add(name)
        seen_details.add(detail_final_url)
        rows.append({"name": name, "duty": duty, "detail_url": detail_final_url})

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
