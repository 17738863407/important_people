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
    "rule_id": "1479",
    "domain": "lyj.hunan.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hunan_forestry_cards_to_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_hunan_forestry_cards_to_detail_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "入口副卡片仅显示姓名，职务必须从对应详情页强字段读取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """在线抓取人物详情页，并对瞬时网络错误进行有限重试。"""
    last_error: requests.RequestException | None = None
    for _ in range(3):
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("详情页在线抓取未执行")


def extract_detail_duty(detail_html: str) -> str:
    """从详情页独立职务字段提取原文，不读取工作职责或个人简介。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for item in soup.select("li.ldjs_com"):
        text = clean_text(item.get_text(" ", strip=True))
        match = re.fullmatch(r"职\s*务\s*[：:]\s*(.+)", text)
        if match:
            return clean_text(match.group(1)).strip("，,；;。 ")
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承主卡片及副卡片顺序，并在线读取对应详情页职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []

    main_card = soup.select_one(".BigLeader")
    if main_card is not None:
        name_node = main_card.select_one(".LeaderIntroduction h2")
        link_node = main_card.select_one("a.BigLeaderPic[href], a.LeaderButton[href]")
        if name_node is not None and link_node is not None:
            candidates.append(
                (
                    clean_name(name_node.get_text(" ", strip=True)),
                    urljoin(final_url, clean_text(str(link_node.get("href", "")))),
                )
            )

    for card in soup.select(".LeaderOther li"):
        link_node = card.select_one("p a[title][href], a.LeaderOtherPic[title][href]")
        if link_node is not None:
            candidates.append(
                (
                    clean_name(str(link_node.get("title", "")) or link_node.get_text(" ", strip=True)),
                    urljoin(final_url, clean_text(str(link_node.get("href", "")))),
                )
            )

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for name, detail_url in candidates:
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        try:
            detail_html = fetch_detail_html(session, detail_url)
        except requests.RequestException:
            continue
        detail_text = clean_text(BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True))
        duty = extract_detail_duty(detail_html)
        if name not in detail_text or not duty:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；"
                    "list=.BigLeader + .LeaderOther li；"
                    "detail=li.ldjs_com label=职务"
                ),
            }
        )

    return records


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
