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
    "rule_id": "3409", "page_type": "人物列表完整页", "structure_group": "shenyang_natural_resources_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_natural_resources_cards_v2",
    "leader_region_selector": ".qw-list", "name_selector": ".yangs直属第1个b内a",
    "duty_selector": ".yangs直属第2个b", "detail_link_selector": ".qw-list直属a[href]",
    "detail_strategy": {"required": True, "mode": "list_dynamic"},
    "risk_flag": "卡片后续p为工作分工，不得混入原始职务",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}
def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按卡片顺序解析姓名、原始职务和直属详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    cards = soup.select(".qw-list")
    if not cards:
        raise RuntimeError("页面没有找到人物卡片")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in cards:
        fields = card.select(".yangs > b")
        if len(fields) != 2:
            raise RuntimeError(f"人物卡片姓名职务字段数量异常：{len(fields)}")
        name_link = fields[0].select_one("a[href]")
        name = clean_text(name_link.get_text(" ", strip=True) if name_link else "")
        evidence = clean_text(fields[1].get_text(" ", strip=True))
        detail_link = card.find("a", href=True, recursive=False)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or detail_link is None:
            raise RuntimeError("人物卡片姓名、职务或详情链接异常")
        detail_url = urljoin(final_url, str(detail_link.get("href", "")).strip())
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
