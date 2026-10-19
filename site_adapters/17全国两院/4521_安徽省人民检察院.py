from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清除排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def is_hidden(node: Tag) -> bool:
    """排除当前节点或祖先中明确隐藏的重复 DOM。"""
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


def clean_target_duty(value: str) -> str:
    """保留院领导列表展示的全部职务，包括各类委员职务。"""
    pieces = [clean_text(item).strip("，,。；;：: ") for item in re.split(r"[、，,；;]", value)]
    return "、".join(item for item in pieces if item)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按页面分组原序抽取院领导及“二巡、二高”详情页中的人物。"""
    if "院领导" not in html:
        try:
            html = html.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    target_headings = []
    for heading in soup.select("#adminTbody .duoji"):
        title = clean_text((heading.select_one("span") or heading).get_text(" ", strip=True))
        if title in {"院领导", "二巡、二高"} and not is_hidden(heading):
            target_headings.append((heading, title))
    if len(target_headings) != 2:
        raise RuntimeError("当前页面未同时找到“院领导”和“二巡、二高”可见分组")

    for heading, title in target_headings:
        leader_list = heading.find_next_sibling("div", class_="arlist")
        if leader_list is None or is_hidden(leader_list):
            raise RuntimeError(f"当前页面未找到“{title}”标题后的可见人物列表")
        for card in leader_list.select("ul > li"):
            if is_hidden(card):
                continue
            link = card.select_one("a[href]")
            if link is None:
                continue
            link_text = clean_text(link.get_text(" ", strip=True))
            href = str(link.get("href") or "").strip()
            target_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""

            if title == "院领导":
                parts = re.split(r"[：:]", link_text, maxsplit=1)
                if len(parts) != 2:
                    raise RuntimeError(f"院领导列表项缺少姓名—职务分隔符：{link_text}")
                names = [clean_text(parts[0]).replace(" ", "")]
                duty = clean_target_duty(parts[1])
                detail_url = target_url if target_url != final_url else ""
                selector_summary = "院领导分组链接文本姓名：职务"
            else:
                if not target_url:
                    raise RuntimeError(f"“{title}”分组列表项缺少有效详情链接：{link_text}")
                from crawler_core.fetcher import fetch_online_html

                detail_html, _ = fetch_online_html(target_url)
                if link_text not in detail_html:
                    try:
                        detail_html = detail_html.encode("latin-1").decode("utf-8")
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        pass
                detail_soup = BeautifulSoup(detail_html, "html.parser")
                region = detail_soup.select_one(".trs_editor_view")
                if region is None or is_hidden(region):
                    raise RuntimeError(f"“{title}”详情页未找到可见正文：{target_url}")
                names = []
                for paragraph in region.select("p"):
                    candidate = clean_text(paragraph.get_text(" ", strip=True)).replace(" ", "")
                    if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", candidate):
                        names.append(candidate)
                duty = clean_target_duty(link_text)
                detail_url = ""
                selector_summary = "二巡、二高分组链接职务；详情正文独立姓名段落"

            if not duty or not names:
                raise RuntimeError(f"“{title}”列表项未提取到完整人物与职务：{link_text}")
            for name in names:
                if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
                    continue
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "evidence": duty,
                        "detail_url": detail_url,
                        "confidence": "high",
                        "parser": str(page_rule.get("parser", "")),
                        "selector_summary": selector_summary,
                    }
                )
                seen.add(name)
    if not rows:
        raise RuntimeError("省院领导人物卡片未提取到目标领导")
    return rows


PAGE_RULE = {
    "rule_id": "4521",
    "domain": "www.ah.jcy.gov.cn",
    "page_type": "院领导分组链接列表",
    "structure_group": "anhui_procuratorate_leader_group_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "在线页面，必要时浏览器渲染",
    "extract_mode": "list_direct",
    "parser": "page_anhui_procuratorate_leader_group_links_v1",
    "leader_region_selector": "#adminTbody中院领导、二巡二高两个.duoji分组及各自紧邻.arlist",
    "name_selector": "院领导链接文本冒号前；二巡二高详情正文独立姓名段落",
    "duty_selector": "院领导链接文本冒号后；二巡二高列表链接标题",
    "detail_link_selector": ".arlist ul > li > a[href]",
    "detail_strategy": {"required": False, "mode": "direct_person_link"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "必须按页面原序覆盖院领导与后部二巡、二高分组；后者从当前列表动态发现详情页并抽取独立姓名段落",
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
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
