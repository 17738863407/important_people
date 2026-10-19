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


PAGE_RULE = {
    "rule_id": "3066", "page_type": "人物目录详情页", "structure_group": "shenyang_petition_detail_first_field_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_petition_detail_first_field_v2",
    "leader_region_selector": ".qw-list", "name_selector": "a.dong_wor[href]",
    "duty_selector": "详情.view排除图片后的首个非空p", "detail_link_selector": "a.dong_wor[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "工作分工不得混入原始职务；不得向原始职务补加机构名",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按卡片顺序在线抓取人物详情中的原始职务首段。"""
    from crawler_core.fetcher import fetch_online_html
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    cards = soup.select(".qw-list")
    if not cards:
        raise RuntimeError("页面没有找到人物卡片")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in cards:
        link = card.select_one("a.dong_wor[href]")
        if link is None:
            raise RuntimeError("人物卡片缺少详情链接")
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True) or str(link.get("title", ""))))
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not detail_url:
            raise RuntimeError("人物卡片姓名或详情链接异常")
        detail_html, detail_final_url = fetch_online_html(detail_url)
        detail = BeautifulSoup(detail_html or "", "html.parser")
        views = detail.select(".view")
        if len(views) != 1:
            raise RuntimeError(f"人物详情正文数量异常：{name}={len(views)}")
        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in views[0].select("p")
            if node.find("img") is None and clean_text(node.get_text(" ", strip=True))
        ]
        if len(paragraphs) < 2 or paragraphs[1].replace(" ", "") not in {"工作分工：", "工作分工:"}:
            raise RuntimeError(f"人物详情职务与工作分工边界异常：{name}")
        evidence = paragraphs[0]
        if not evidence or name in seen_names:
            raise RuntimeError(f"人物详情职务为空或姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_final_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
