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
    "rule_id": "2857", "page_type": "人物列表完整页", "structure_group": "shenyang_foreign_affairs_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_foreign_affairs_cards_v2",
    "leader_region_selector": ".main-wrap1 .ry-xq", "name_selector": ".yangs直属非空b第1项",
    "duty_selector": ".yangs直属非空b第2项", "detail_link_selector": "同级前置.qw-list1 a[href]",
    "detail_strategy": {"required": True, "mode": "list_dynamic"},
    "risk_flag": "卡片后续p为工作分工，不得混入原始职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片顺序解析强结构姓名、原始职务和相邻详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    cards = soup.select(".main-wrap1 .ry-xq")
    if not cards:
        raise RuntimeError("页面没有找到人物卡片")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in cards:
        fields = [clean_text(node.get_text(" ", strip=True)) for node in card.select(".yangs > b")]
        fields = [value for value in fields if value]
        if len(fields) != 2:
            raise RuntimeError(f"人物卡片非空姓名职务字段数量异常：{len(fields)}")
        name, evidence = fields
        link_box = card.find_previous_sibling("div", class_="qw-list1")
        link = link_box.select_one("a[href]") if link_box else None
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or link is None:
            raise RuntimeError("人物卡片姓名、职务或详情链接异常")
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        if not detail_url or detail_url == final_url or name in seen_names:
            raise RuntimeError(f"人物详情链接异常或姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
