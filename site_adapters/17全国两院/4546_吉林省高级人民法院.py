from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4546", "page_type": "省高级法院领导链接列表",
    "structure_group": "jilin_high_court_titled_links_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_jilin_high_court_titled_links_v1",
    "leader_region_selector": ".list_br ul",
    "name_selector": "span.left a[title]标题末尾姓名", "duty_selector": "span.left a[title]标题中的完整职务",
    "detail_link_selector": "span.left a[title][href]", "detail_strategy": {"required": True, "mode": "list_link"}, "locator_strategy": "custom_parse_page",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅解析法院领导栏目中带title的领导详情链接，按列表原序保留执行局局长、专职审判委员会委员和法官培训学院院长。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select(".list_br ul li span.left a[title][href]"):
        title = compact(link.get("title") or link.get_text(" ", strip=True))
        match = re.fullmatch(
            r"(?P<duty>.+(?:院长|副院长|主任|组长|局长|委员))"
            r"(?P<name>[\u3400-\u9fff·]{2,6})",
            title,
        )
        if match is None:
            continue
        duty = match.group("duty")
        rows.append({"name": match.group("name"), "duty": duty, "evidence": duty, "detail_url": urljoin(final_url, str(link.get("href", ""))), "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".list_br内span.left标题链接按DOM原序拆分完整职务与末尾姓名"})
    if not rows:
        raise RuntimeError("法院领导列表未提取到带标题的领导详情链接")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
