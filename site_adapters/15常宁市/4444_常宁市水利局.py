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
    "rule_id": "4444",
    "page_type": "部门领导列表及详情页",
    "structure_group": "hnchangning_department_leader_details_v1",
    "load_mode": "浏览器渲染后跳转领导列表",
    "extract_mode": "custom",
    "parser": "page_inline_hnchangning_department_leader_details_v1",
    "leader_region_selector": ".contain_right .contain_ul",
    "name_selector": ".inner_details h3 与简历字段中的姓名",
    "duty_selector": ".inner_details .inner_box p 的职务字段",
    "detail_link_selector": ".contain_right .contain_ul > li a[href]",
    "detail_strategy": {"required": True, "mode": "directory_to_detail"},
    "risk_flag": "静态 HTTP 当前返回 412；入口渲染后跳转领导列表，职务仅取详情页明确职务字段。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页排版空白，但不改写字段语义。"""
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


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


def extract_detail_fields(html: str, detail_url: str) -> tuple[str, str]:
    """从人物详情页的标题/简历与明确职务字段提取姓名和原始职务。"""
    root = BeautifulSoup(html, "html.parser").select_one(".inner_details")
    if root is None:
        raise RuntimeError(f"人物详情页缺少 .inner_details：{detail_url}")
    duty = ""
    biography = ""
    for paragraph in root.select(".inner_box p"):
        if not is_visible(paragraph):
            continue
        text = clean_text(paragraph.get_text(" ", strip=True))
        if re.match(r"^职务\s*[:：]", text):
            duty = re.sub(r"^职务\s*[:：]\s*", "", text).rstrip("。；; ")
        elif re.match(r"^简历\s*[:：]", text):
            biography = re.sub(r"^简历\s*[:：]\s*", "", text)
    if not duty:
        raise RuntimeError(f"人物详情页缺少明确职务字段：{detail_url}")
    name = re.sub(r"\s+", "", re.split(r"[,，]", biography, maxsplit=1)[0]) if biography else ""
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
        heading = clean_text(root.select_one("h3").get_text(" ", strip=True)) if root.select_one("h3") else ""
        match = re.search(r"([\u3400-\u9fff·]{2,6})$", heading)
        name = match.group(1) if match else ""
    if not name:
        raise RuntimeError(f"人物详情页无法从标题或简历确认姓名：{detail_url}")
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导列表原始顺序逐页提取姓名、职务和真实详情链接。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".contain_right .contain_ul")
    if region is None:
        raise RuntimeError("渲染页面缺少领导列表 .contain_right .contain_ul")
    final_host = str(urlparse(final_url).hostname or "").casefold()
    detail_urls: list[str] = []
    for anchor in region.select(":scope > li a[href]"):
        detail_url = urljoin(final_url, str(anchor.get("href") or ""))
        parsed = urlparse(detail_url)
        if is_visible(anchor) and str(parsed.hostname or "").casefold() == final_host and re.search(r"/gzjg/ldxx/\d{8}/i\d+\.html$", parsed.path) and detail_url not in detail_urls:
            detail_urls.append(detail_url)
    if not detail_urls:
        raise RuntimeError("领导列表未发现真实人物详情链接")
    rows: list[dict[str, str]] = []
    for detail_url in detail_urls:
        result = fetch_html_with_strategy(detail_url, strategy="playwright", timeout=45)
        name, duty = extract_detail_fields(result.html, result.final_url)
        rows.append({"name": name, "duty": duty, "detail_url": result.final_url, "evidence": duty, "parser": str(page_rule["parser"]), "selector_summary": "领导列表人物链接→详情页明确职务字段"})
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
