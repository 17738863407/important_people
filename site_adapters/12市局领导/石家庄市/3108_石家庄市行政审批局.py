from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3108", "page_type": "人物列表完整页", "structure_group": "sjz_approval_strong_name_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "sjz_approval_strong_name_v2",
    "leader_region_selector": "#conN > div", "name_selector": "人物div唯一strong中的姓名",
    "duty_selector": "同一人物div移除strong后的完整原文", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面无人物详情链接，入口页不得写入详情链接",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅合并网页排版空白，不改变原始职务语义。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物div中的唯一strong姓名和同div余文解析。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#conN")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文数量异常：{len(regions)}")
    items = regions[0].find_all("div", recursive=False)
    if not items:
        raise RuntimeError("领导正文没有直接人物项")

    records: list[object] = []
    seen_names: set[str] = set()
    for item in items:
        strong_nodes = item.find_all("strong")
        if len(strong_nodes) != 1:
            raise RuntimeError(f"人物项strong数量异常：{len(strong_nodes)}")
        name = re.sub(r"\s+", "", clean_text(strong_nodes[0].get_text(" ", strip=True))).rstrip("：:")
        item_copy = BeautifulSoup(str(item), "html.parser")
        copied_strong = item_copy.find("strong")
        if copied_strong is None:
            raise RuntimeError("复制人物项后未找到strong")
        copied_strong.decompose()
        evidence = clean_text(item_copy.get_text(" ", strip=True))
        evidence = evidence.rstrip("。")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence or name in seen_names:
            raise RuntimeError(f"人物姓名、职务异常或姓名重复：{name}")
        if item.select_one("a[href]") is not None:
            raise RuntimeError(f"人物项出现未审计链接：{name}")

        seen_names.add(name)
        records.append(PersonRecord(
            organization=page_rule["organization"], url=page_rule["url"], name=name,
            duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"],
        ))
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
