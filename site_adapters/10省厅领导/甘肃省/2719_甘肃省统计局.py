from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def clean_text(value: str) -> str:
    """压缩人物卡片的排版空白，不改变原文语义。"""
    text = " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def is_hidden(node: Tag) -> bool:
    """排除节点及祖先明确隐藏的备用 DOM。"""
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


def same_origin(reference_url: str, candidate_url: str) -> bool:
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (reference.scheme, reference.netloc) == (candidate.scheme, candidate.netloc)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导简介名单顺序抓取详情，只提取同一人物的现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "lxml")
    leader_list = soup.select_one(str(page_rule["leader_region_selector"]))
    if leader_list is None:
        raise RuntimeError("未找到渲染后的领导简介列表")

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for anchor in leader_list.select(":scope > li > a[href]"):
        if is_hidden(anchor):
            continue
        name = clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or name in seen_names:
            continue

        detail_url = urljoin(final_url, str(anchor.get("href", "")))
        detail_path = urlsplit(detail_url).path
        if not same_origin(final_url, detail_url) or not re.fullmatch(
            r"/tjj/c109477/\d{6}/\d+\.shtml",
            detail_path,
        ):
            raise RuntimeError(f"{name}详情路径不符合当前领导栏目结构")

        result = fetch_html_with_strategy(
            detail_url,
            strategy="chrome",
            timeout=60,
            browser_render_wait_ms=2000,
        )
        detail_soup = BeautifulSoup(result.html, "lxml")
        content = detail_soup.select_one("#ContentDetail")
        paragraphs = (
            [clean_text(item.get_text(" ", strip=True)) for item in content.select("p")]
            if content is not None
            else []
        )
        current_sentence = next(
            (item for item in paragraphs if item.startswith(f"{name}，") and "现任" in item),
            "",
        )
        match = re.search(r"现任(?P<duty>[^。；]{2,120})。", current_sentence)
        if not match:
            raise RuntimeError(f"{name}详情页未找到可回指的现任职务句")
        duty = clean_text(match.group("duty"))

        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_gansu_stats_list_detail_current_v2",
                "selector_summary": "entry=ul.top_ldjjlist按DOM顺序；detail=#ContentDetail内姓名开头的现任句；排除分工段",
            }
        )
    return records


PAGE_RULE = {
    "rule_id": "2719",
    "page_type": "人物目录详情页",
    "structure_group": "gansu_stats_list_detail_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_stats_list_detail_current_v2",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.top_ldjjlist",
    "name_selector": ":scope > li > a[title]",
    "duty_selector": "#ContentDetail p内姓名开头的现任句",
    "detail_link_selector": ":scope > li > a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_content_selector": "#ContentDetail", "max_detail_links": 15},
    "risk_flag": "普通HTTP返回412；入口仅含姓名和详情链接，职务必须从对应详情当前人物现任句提取，分工段不得进入依据",
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
