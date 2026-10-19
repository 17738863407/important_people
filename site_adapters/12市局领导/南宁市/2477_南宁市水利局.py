from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2477",
    "page_type": "人物目录详情页",
    "structure_group": "nanning_water_list_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_list_then_detail_http",
    "parser": "page_nanning_water_list_detail_v2",
    "leader_region_selector": "领导班子栏目人物链接列表",
    "name_selector": "人物链接文本",
    "duty_selector": "详情正文第一个姓名职务段",
    "detail_link_selector": "领导班子目录内/t人物链接",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "max_detail_links": 30},
    "risk_flag": "历史脚本依赖详情快照和固定候选链接；必须在线动态发现列表并只读取详情首个姓名职务段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {"css": {"leader_region_selector": "领导班子栏目人物链接列表", "detail_link_selector": "目录内/t人物链接", "detail_content_selector": "#UCAP-CONTENT, .TRS_UEDITOR, .content"}, "api": {"enabled": False, "reason": "人物目录和一对一详情均由静态HTML提供"}},
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_people(html: str, final_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    people: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        name = normalize_layout(anchor.get_text(" ", strip=True)).replace(" ", "")
        href = str(anchor.get("href", "")).strip()
        detail_url = urljoin(final_url, href)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or "/ldbz/t" not in detail_url or name in seen:
            continue
        seen.add(name)
        people.append((name, detail_url))
    return people


def parse_detail(html: str, expected_name: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#UCAP-CONTENT") or soup.select_one(".TRS_UEDITOR") or soup.select_one(".content")
    if region is None:
        return ""
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        if text.startswith(expected_name) and len(text) <= 120 and re.search(r"(?:书记|局长|党组|调研员|巡视员)", text):
            return text
    return ""


def clean_detail_duty(value: str, expected_name: str) -> str:
    """从已定位的姓名职务短段移除姓名及其紧邻称谓、分隔符。"""
    text = normalize_layout(value)
    text = re.sub(rf"^{re.escape(expected_name)}(?:同志)?[：:，,、\s]*", "", text)
    return text.strip("：:，,、 ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    people = discover_people(html, final_url)
    if not people:
        return []
    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    for name, detail_url in people:
        raw_evidence = parse_detail(fetch_html_with_strategy(detail_url, strategy="requests").html, name)
        evidence = clean_detail_duty(raw_evidence, name)
        if not evidence:
            raise RuntimeError(f"人物详情页缺少可回指的首个姓名职务段：{detail_url}")
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": detail_url, "parser": str(page_rule.get("parser", "")), "selector_summary": "人物目录链接按DOM顺序动态发现；逐详情取首个姓名职务短段"})
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
