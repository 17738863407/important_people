from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2998",
    "page_type": "人物卡片完整页",
    "structure_group": "sichuan_health_leader_cards_full_page_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "field_pair",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".wy_ld_cont dl",
    "name_selector": "dt a[href]",
    "duty_selector": "dd.fontSt",
    "detail_link_selector": "dt a[href]",
    "content_scope": {
        "include_selectors": [".wy_ld_cont"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "same_card_link"},
    "risk_flag": "按当前用户验收口径采集规则入口全部领导卡片；保持页面原序和完整原始职务，不按职务关键词筛除人物",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩页面排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口页面顺序提取全部领导卡片及其完整原始职务。"""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".wy_ld_cont dl")
    if not cards:
        from crawler_core.fetcher import fetch_by_raw_requests

        entrance_url = str(page_rule.get("url") or "")
        if not entrance_url:
            raise ValueError("规则主表未注入省卫生健康委领导入口")
        raw_result = fetch_by_raw_requests(entrance_url, timeout=30)
        final_url = raw_result.final_url
        soup = BeautifulSoup(raw_result.html, "lxml")
        cards = soup.select(".wy_ld_cont dl")
    if not cards:
        raise ValueError("省卫生健康委领导页的原始HTML未发现领导卡片")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in cards:
        name_link = card.select_one("dt a[href]")
        duty_node = card.select_one("dd.fontSt")
        if name_link is None or duty_node is None:
            continue
        name = re.sub(r"\s+", "", normalize_text(name_link.get_text(" ", strip=True)))
        duty = normalize_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            raise ValueError(f"领导卡片姓名格式异常：{name!r}")
        if name in seen_names:
            raise ValueError(f"领导卡片出现重复姓名：{name}")
        detail_url = urljoin(final_url, str(name_link.get("href") or "").strip())
        scheme = urlparse(detail_url).scheme.lower()
        if scheme not in {"http", "https"} or detail_url == final_url:
            raise ValueError(f"领导卡片详情链接无效：{detail_url!r}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
            }
        )
    if not rows:
        raise ValueError("当前入口未解析出有效领导卡片")
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
