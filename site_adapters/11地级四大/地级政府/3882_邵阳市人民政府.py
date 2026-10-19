from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3882",
    "page_type": "职务分组人物卡片页",
    "structure_group": "shaoyang_government_grouped_cards_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_shaoyang_government_groups_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".slds-item, .ldzc_div_img",
    "name_selector": ".slds-list > a.imgHover1[href] > p, ul > li > a[href]",
    "duty_selector": ".slds-name, .ldzc_div_img_title",
    "detail_link_selector": ".slds-list > a.imgHover1[href], ul > li > a[href]",
    "risk_flag": "采集器会跳转移动版；兼容桌面与移动结构并排除源码注释中的旧链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def compact_text(value: object) -> str:
    """删除姓名或短职务标题中的纯排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def same_page(reference_url: str, candidate_url: str) -> bool:
    """忽略查询和片段比较入口与候选详情路径。"""
    reference = urlsplit(reference_url)
    candidate = urlsplit(candidate_url)
    return (
        reference.scheme.lower(),
        reference.netloc.lower(),
        reference.path.rstrip("/"),
    ) == (
        candidate.scheme.lower(),
        candidate.netloc.lower(),
        candidate.path.rstrip("/"),
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按最终页面的职务标题与人物列表顺序提取领导信息。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()

    def append_link(link: object, duty: str) -> None:
        """将当前职务标题下的一个可见人物链接追加到结果。"""
        if not duty:
            return
        name_node = link.select_one("p")
        name = compact_text(
            name_node.get_text(" ", strip=True)
            if name_node is not None
            else link.get_text(" ", strip=True)
        )
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen_names:
            return
        if not detail_url or same_page(page_rule["url"], detail_url):
            detail_url = ""

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "最终页职务标题及其紧随人物列表链接",
            }
        )

    desktop_groups = soup.select(".slds-item")
    if desktop_groups:
        for group in desktop_groups:
            duty_node = group.find("div", class_="slds-name", recursive=False)
            duty = compact_text(duty_node.get_text(" ", strip=True) if duty_node else "")
            for link in group.select(".slds-list > a.imgHover1[href]"):
                append_link(link, duty)
    else:
        mobile_regions = soup.select(".ldzc_div_img")
        for region in mobile_regions:
            current_duty = ""
            for child in region.find_all(recursive=False):
                classes = set(child.get("class") or [])
                if child.name == "div" and "ldzc_div_img_title" in classes:
                    current_duty = compact_text(child.get_text(" ", strip=True))
                    continue
                if child.name != "ul" or not current_duty:
                    continue
                for link in child.select(":scope > li > a[href]"):
                    append_link(link, current_duty)

    if not rows:
        raise RuntimeError("最终页面未找到可对应的职务标题与人物链接")
    return rows


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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
