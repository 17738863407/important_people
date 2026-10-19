from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2861",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_culture_list_detail_title_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_list_then_detail_http",
    "parser": "page_nanning_culture_list_detail_title_v2",
    "leader_region_selector": "领导简介栏目./t人物链接",
    "name_selector": "详情首段姓名同志标签",
    "duty_selector": "详情首段冒号后至职责动词前职务",
    "detail_link_selector": "a[href^='./t']",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 30},
    "risk_flag": "列表文本为职务在前姓名在后，二字三字姓名边界不稳定；必须逐详情以姓名同志和职责动词边界解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "领导简介栏目./t人物链接", "detail_link_selector": "a[href^='./t']", "detail_content_selector": "#UCAP-CONTENT, .TRS_UEDITOR, .content"}, "api": {"enabled": False, "reason": "人物列表和一对一详情均由静态HTML提供"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_details(html: str, final_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href", "")).strip()
        label = normalize_layout(anchor.get_text(" ", strip=True))
        if not href.startswith("./t") or re.search(r"(?:书记|局长|副局长|调研员)", label) is None:
            continue
        url = urljoin(final_url, href)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def parse_detail(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#UCAP-CONTENT") or soup.select_one(".TRS_UEDITOR") or soup.select_one(".content")
    if region is None:
        return "", ""
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})同志：(?P<rest>.+)", text)
        if match is None:
            continue
        duty = re.split(r"(?=领导和|主持|负责|主管|分管|配合|协助|联系)", match.group("rest"), maxsplit=1)[0].strip(" ，。；")
        if not duty or len(duty) > 100 or re.search(r"(?:书记|局长|副局长|党组|调研员|科长|主任委员)", duty) is None:
            continue
        return match.group("name"), duty
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    detail_urls = discover_details(html, final_url)
    if not detail_urls:
        return []
    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for detail_url in detail_urls:
        name, evidence = parse_detail(fetch_html_with_strategy(detail_url, strategy="requests").html)
        if not name or not evidence:
            raise RuntimeError(f"人物详情页缺少可回指的姓名同志职务前缀：{detail_url}")
        if name in seen:
            continue
        seen.add(name)
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "栏目人物链接按DOM顺序；逐详情首段提取姓名同志后至职责动词前职务"})
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

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
