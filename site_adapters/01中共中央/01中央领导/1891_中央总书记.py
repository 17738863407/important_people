from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return " ".join((value or "").replace("\xa0", " ").split()).strip()


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先上明确隐藏的备用 DOM。"""
    current: Tag | None = node
    while current is not None:
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        if "display:none" in style or "visibility:hidden" in style:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def extract_current_duty(detail_url: str, name: str) -> tuple[str, str]:
    """进入人物报道页的“查看简历”二级页面，提取“现任”现职。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    report_result = fetch_by_raw_requests(detail_url, timeout=30)
    report_soup = BeautifulSoup(report_result.html, "lxml")
    resume_icon = report_soup.select_one("a[href] img.resumeicon, a[href] img[src*='Resumeicon']")
    resume_link = resume_icon.find_parent("a", href=True) if resume_icon else None
    if resume_link is None:
        raise RuntimeError(f"{name}人物报道页未找到“查看简历”链接")
    resume_url = urljoin(report_result.final_url, str(resume_link.get("href", "")))
    result = fetch_by_raw_requests(resume_url, timeout=30)
    for _ in range(3):
        redirect = re.search(r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]", result.html)
        if redirect is None:
            break
        next_url = urljoin(result.final_url, redirect.group(1))
        if next_url == result.final_url:
            break
        result = fetch_by_raw_requests(next_url, timeout=30)
    soup = BeautifulSoup(result.html, "lxml")
    profile = soup.select_one("#detail")
    if profile is None:
        raise RuntimeError(f"{name}简历页未找到正文区域")
    match = re.search(r"现任\s*([^。！？!?]+)", clean_text(profile.get_text(" ", strip=True)))
    if match is None:
        raise RuntimeError(f"{name}简历页正文未找到“现任”职务")
    return match.group(1).strip(), result.final_url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """仅解析“中央委员会总书记”最小分组并验证人物报道专页。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "lxml")
    section = soup.select_one("div.part01.column-box")
    if section is None:
        raise RuntimeError("未找到中央委员会总书记分组")
    heading_node = section.select_one(":scope > .lmt01 h2 > .tit")
    duty = clean_text(heading_node.get_text(" ", strip=True)) if heading_node else ""
    if duty != "中央委员会总书记":
        raise RuntimeError(f"目标分组标题不一致：{duty or '空'}")

    cards = [
        card
        for card in section.select(":scope > .person-box")
        if not is_hidden(card)
    ]
    if len(cards) != 1:
        raise RuntimeError(f"中央委员会总书记分组可见人物卡片数异常：{len(cards)}")

    anchor = cards[0].select_one(":scope > a[href]")
    name_node = cards[0].select_one(".name")
    if anchor is None or name_node is None:
        raise RuntimeError("目标人物卡片缺少姓名或详情链接")
    name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,6}", name):
        raise RuntimeError(f"目标人物姓名字符异常：{name or '空'}")

    detail_url = urljoin(final_url, str(anchor.get("href", "")))
    detail_parts = urlsplit(detail_url)
    if detail_parts.netloc.lower() != "www.news.cn" or not re.fullmatch(
        r"/politics/leaders/[a-z0-9_-]+/index\.htm",
        detail_parts.path,
    ):
        raise RuntimeError("人物详情链接不符合新华网领导报道专页结构")

    fetch_result = fetch_by_raw_requests(detail_url, timeout=30)
    detail_soup = BeautifulSoup(fetch_result.html, "lxml")
    detail_title = clean_text(detail_soup.title.get_text(" ", strip=True)) if detail_soup.title else ""
    if not detail_title.startswith(name) or "报道专集" not in detail_title:
        raise RuntimeError("人物详情页标题与目录姓名不一致")

    current_duty, current_detail_url = extract_current_duty(fetch_result.final_url, name)
    return [
        {
            "name": name,
            "duty": current_duty,
            "detail_url": current_detail_url,
            "evidence": current_duty,
            "confidence": "high",
            "parser": "page_inline_xinhua_general_secretary_group_v1",
        }
    ]


PAGE_RULE = {
    "rule_id": "1891",
    "page_type": "职务分组名单页",
    "structure_group": "xinhua_general_secretary_part01",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_xinhua_general_secretary_group_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "div.part01.column-box",
    "name_selector": ":scope > .person-box .name",
    "duty_selector": ":scope > .lmt01 h2 > .tit",
    "detail_link_selector": ":scope > .person-box > a[href]",
    "risk_flag": "同页包含多个中央领导机构分组；仅 part01 精确标题和唯一可见人物卡片进入结果",
    "confidence": "high",
}


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
