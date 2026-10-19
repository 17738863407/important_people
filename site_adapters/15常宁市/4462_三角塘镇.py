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
    "rule_id": "4462",
    "page_type": "乡镇领导信息列表",
    "structure_group": "changning_township_leader_list_v1",
    "load_mode": "浏览器跳转后的渲染DOM",
    "extract_mode": "list_direct",
    "parser": "page_inline_changning_township_leader_list_v1",
    "leader_region_selector": ".contain_ul",
    "name_selector": ".contain_ul > li > a[href]（冒号后）",
    "duty_selector": ".contain_ul > li > a[href]（冒号前）",
    "detail_link_selector": ".contain_ul > li > a[href]",
    "detail_strategy": {"required": True, "mode": "list_link"},
    "risk_flag": "入口页会跳转到领导信息栏目；仅解析可见领导列表，不读取日期、分页、导航、简历或分工。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按领导列表 DOM 顺序拆分“完整职务：姓名”，并保留真实个人页链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        raise RuntimeError("领导信息页缺少 .contain_ul 列表")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select(":scope > li"):
        if item.has_attr("hidden") or "display:none" in str(item.get("style") or "").replace(" ", "").lower():
            continue
        anchor = item.find("a", href=True)
        if anchor is None:
            continue
        text = " ".join(anchor.get_text(" ", strip=True).split())
        match = re.fullmatch(r"(?P<duty>[^：:]{2,80})\s*[：:]\s*(?P<name>[\u3400-\u9fff·]{2,6})", text)
        if match is None:
            continue
        name = match.group("name")
        duty = match.group("duty").strip()
        detail_url = urljoin(final_url, str(anchor["href"]).strip())
        parsed = urlparse(detail_url)
        if parsed.scheme not in {"http", "https"} or "/gzjg/ldxx/" not in parsed.path:
            raise RuntimeError(f"人物链接不是领导信息详情页：{detail_url}")
        if name in seen_names:
            continue
        seen_names.add(name)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url})

    if not rows:
        raise RuntimeError("领导信息列表未解析出有效人物")
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
