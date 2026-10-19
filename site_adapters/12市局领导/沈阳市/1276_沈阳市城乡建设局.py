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
    "rule_id": "1276", "page_type": "人物列表完整页", "structure_group": "shenyang_urban_construction_cards_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_urban_construction_cards_v2",
    "leader_region_selector": ".xxgk_rul .qw-list", "name_selector": ".yangs b a[href]",
    "duty_selector": ".qw-list1_bot中办公地点锚点之前", "detail_link_selector": ".yangs b a[href]",
    "detail_strategy": {"required": True, "mode": "list_item_link"},
    "risk_flag": "职务与办公地点、办公时间、工作分工共处同一p；只保留办公地点锚点前的原始文本并保留标点",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物卡片顺序提取姓名、职务边界和独立详情链接。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    for card in soup.select(".xxgk_rul .qw-list"):
        name_link = card.select_one(".yangs b a[href]")
        duty_node = card.select_one(".qw-list1_bot")
        name = re.sub(r"\s+", "", clean_text(name_link.get_text(" ", strip=True) if name_link else ""))
        combined = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if "办公地点" not in combined:
            raise RuntimeError(f"人物卡片缺少职务与办公信息边界：{name or '未知姓名'}")
        evidence = combined.split("办公地点", 1)[0].strip().removesuffix("。")
        href = clean_text(name_link.get("href", "") if name_link else "")
        detail_url = urljoin(final_url or page_rule["url"], href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("人物卡片姓名或职务字段异常")
        if not detail_url or detail_url == (final_url or page_rule["url"]):
            raise RuntimeError(f"人物详情链接异常：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物卡片姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
    if not records:
        raise RuntimeError("当前页面未提取到人物卡片")
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
