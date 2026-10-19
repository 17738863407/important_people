from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4450",
    "page_type": "部门领导列表链接",
    "structure_group": "hnchangning_department_leader_link_titles_v1",
    "load_mode": "浏览器渲染后跳转领导列表",
    "extract_mode": "custom",
    "parser": "page_inline_hnchangning_department_leader_link_titles_v1",
    "leader_region_selector": ".contain_right .contain_ul",
    "name_selector": "领导详情链接标题冒号后的姓名",
    "duty_selector": "领导详情链接标题冒号前的职务",
    "detail_link_selector": ".contain_right .contain_ul > li a[href]",
    "detail_strategy": {"required": True, "mode": "dynamic_link"},
    "risk_flag": "静态 HTTP 当前返回 412；列表标题含职级，作为明确职务证据完整保留。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def is_visible(node: Tag) -> bool:
    """排除节点及祖先上的明确隐藏标记。"""
    current: Tag | None = node
    while isinstance(current, Tag):
        style = str(current.get("style") or "").replace(" ", "").casefold()
        classes = {str(item).casefold() for item in current.get("class") or []}
        if current.has_attr("hidden") or str(current.get("aria-hidden") or "").casefold() == "true" or "display:none" in style or "visibility:hidden" in style or classes.intersection({"hidden", "hide", "showno"}):
            return False
        current = current.parent if isinstance(current.parent, Tag) else None
    return True


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按列表 DOM 原始顺序解析“完整职务：姓名”链接标题。"""
    region = BeautifulSoup(html, "html.parser").select_one(".contain_right .contain_ul")
    if region is None:
        raise RuntimeError("渲染页面缺少领导列表 .contain_right .contain_ul")
    final_host = str(urlparse(final_url).hostname or "").casefold()
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in region.select(":scope > li a[href]"):
        if not is_visible(anchor):
            continue
        detail_url = urljoin(final_url, str(anchor.get("href") or ""))
        parsed = urlparse(detail_url)
        if str(parsed.hostname or "").casefold() != final_host or not re.search(r"/gzjg/ldxx/\d{8}/i\d+\.html$", parsed.path):
            continue
        title = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
        parts = re.split(r"[:：]", title, maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError(f"领导链接标题不符合“职务：姓名”结构：{title}")
        duty = parts[0].strip().rstrip("。；; ")
        name = re.sub(r"\s+", "", parts[1])
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
            raise RuntimeError(f"领导链接标题字段无效：{title}")
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty, "parser": str(page_rule["parser"]), "selector_summary": "领导列表链接标题中的完整职务：姓名"})
    if not rows:
        raise RuntimeError("领导列表未解析出有效人物记录")
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
