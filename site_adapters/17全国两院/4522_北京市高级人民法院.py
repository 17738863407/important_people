from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清除排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def is_hidden(node: Tag) -> bool:
    """排除当前节点或祖先中的明确隐藏 DOM。"""
    for current in (node, *node.parents):
        if not isinstance(current, Tag):
            continue
        classes = " ".join(str(item).lower() for item in current.get("class", []))
        style = str(current.get("style", "")).replace(" ", "").lower()
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or re.search(r"(^|\s)(hide|hidden|dn)(\s|$)", classes):
            return True
    return False


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按院领导信息列表原序拆分完整职务与末尾姓名。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = next(
        (
            node
            for node in soup.select(".content")
            if clean_text((node.select_one(".title h2") or node).get_text(" ", strip=True)).startswith("院领导信息")
        ),
        None,
    )
    if region is None:
        raise RuntimeError("未找到标题为“院领导信息”的内容区域")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in region.select("ul li .left a[title][href]"):
        if is_hidden(link):
            continue
        text = clean_text(str(link.get("title") or link.get_text(" ", strip=True)))
        match = re.fullmatch(r"(?P<duty>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,10})", text)
        if match is None:
            raise RuntimeError(f"院领导列表项无法拆分职务与姓名：{text}")
        name = match.group("name")
        duty = clean_text(match.group("duty")).strip("，,。；; ")
        if name in seen:
            continue
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(final_url, href)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url if detail_url != final_url else "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "院领导信息列表可见项原序；链接标题末尾姓名、此前完整职务；领导区委员同样保留",
            }
        )
        seen.add(name)
    if not rows:
        raise RuntimeError("院领导信息列表未提取到目标领导")
    return rows


PAGE_RULE = {
    "rule_id": "4522",
    "domain": "bjgy.bjcourt.gov.cn",
    "page_type": "职务姓名合并列表",
    "structure_group": "beijing_high_court_duty_name_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_beijing_high_court_duty_name_links_v1",
    "leader_region_selector": ".content中标题为院领导信息的区域",
    "name_selector": "ul li .left a[title][href]标题末尾姓名",
    "duty_selector": "ul li .left a[title][href]标题姓名前文本",
    "detail_link_selector": "ul li .left a[title][href]",
    "detail_strategy": {"required": False, "mode": "direct_person_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "相邻导航含审判委员会名录；仅解析院领导信息正文列表，并保留该领导区内全部委员",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
