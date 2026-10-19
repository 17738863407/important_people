from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PAGE_RULE = {
    "rule_id": "2282",
    "page_type": "人物目录详情页",
    "structure_group": "scsqw_leader_title_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "page_local_parse_page",
    "collector": "raw_http",
    "parser": "page_local_parse_page",
    "leader_region_selector": "ul.articlePicPageList",
    "name_selector": "li > .title > a.tit 文本末尾姓名",
    "duty_selector": "li > .title > a.tit 文本姓名前缀",
    "detail_link_selector": "li > .title > a.tit[href]",
    "risk_flag": "搜索函数含未执行location赋值，须保留原始HTML；姓名职务共用标题节点",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    """确定性压缩网页排版空白。"""
    return re.sub(r"\s+", " ", value).strip()


def _build_session() -> requests.Session:
    """建立带有限GET重试的同站会话。"""
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
    return session


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析领导卡片的职务姓名标题，并在线核验独立简介页。"""
    del page_rule
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("ul.articlePicPageList > li")
    if not cards:
        raise ValueError("领导简介页未发现人物卡片")

    session = _build_session()
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_details: set[str] = set()
    entry_path = urlparse(final_url).path.rstrip("/") + "/"

    for card in cards:
        title_anchor = card.select_one(":scope > .title > a.tit[href]")
        if title_anchor is None:
            raise ValueError("人物卡片缺少职务姓名标题链接")
        card_text = _clean_text(title_anchor.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,6})", card_text)
        if match is None:
            raise ValueError(f"人物卡片无法按职务与末尾姓名拆分：{card_text}")
        duty, name = match.groups()
        if name in seen_names:
            raise ValueError(f"领导列表出现重复姓名：{name}")

        detail_url = urljoin(final_url, title_anchor["href"])
        detail_path = urlparse(detail_url).path
        if not detail_path.startswith(entry_path) or "/content_" not in detail_path:
            raise ValueError(f"人物链接不是当前领导目录的独立简介页：{detail_url}")
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        detail_text = re.sub(r"\s+", "", detail_soup.get_text(" ", strip=True))
        if name not in detail_text:
            raise ValueError(f"独立简介页无法回指人物姓名：{response.url}")
        if response.url in seen_details:
            raise ValueError(f"多名人物复用了同一详情页：{response.url}")

        seen_names.add(name)
        seen_details.add(response.url)
        rows.append({"name": name, "duty": duty, "detail_url": response.url})

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
