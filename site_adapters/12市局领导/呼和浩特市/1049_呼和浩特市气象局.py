from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1049",
    "page_type": "人物列表完整页",
    "structure_group": "huhhot_relative_fragment_leader_list_v1",
    "reuse_scope": "same_platform_structure",
    "load_mode": "动态XHR返回HTML片段",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "xhr_html",
    "parser": "huhhot_relative_fragment_leader_list_v1",
    "leader_region_selector": "入口cid对应data-url返回片段中的.leaderList",
    "name_selector": ".leaderList li a[href] p:last-of-type",
    "duty_selector": ".leaderList li a[href] p:first-of-type",
    "detail_link_selector": ".leaderList li a[href]",
    "detail_strategy": {"required": False, "mode": "same_card_independent_detail", "same_host_only": True},
    "risk_flag": "入口只含动态容器，须从当前cid栏目元素发现相对片段路径后限定leaderList解析",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """由入口cid动态发现HTML片段，并按leaderList卡片原序提取。"""
    soup = BeautifulSoup(html, "html.parser")
    cid = parse_qs(urlparse(final_url).query).get("cid", [""])[0]
    if not cid:
        raise ValueError("规则入口未提供栏目cid")
    column = soup.select_one(f"a.muluShow[cid='{cid}'][data-url]")
    if column is None:
        raise ValueError("入口页未找到当前cid对应的动态栏目路径")
    fragment_url = urljoin(final_url, str(column.get("data-url", "")))
    host = urlparse(final_url).netloc.lower()
    if urlparse(fragment_url).netloc.lower() != host:
        raise ValueError("动态栏目片段不属于规则入口站点")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    response = session.get(fragment_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    region = BeautifulSoup(response.text, "html.parser").select_one(".leaderList")
    if region is None:
        raise ValueError("动态栏目片段未返回leaderList领导区域")

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in region.select("li a[href]"):
        fields = [clean_text(node.get_text(" ", strip=True)) for node in anchor.select("p")]
        if len(fields) < 2:
            continue
        duty, name = fields[0], re.sub(r"\s+", "", fields[-1])
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(fragment_url, str(anchor.get("href", "")))
        if urlparse(detail_url).netloc.lower() != host or detail_url in {final_url, fragment_url}:
            detail_url = ""
        seen.add(name)
        records.append({"name": name, "duty": duty, "evidence": duty, "detail_url": detail_url,
                        "selector_summary": "入口cid动态栏目片段；leaderList卡片DOM原序；首末p强字段"})
    if not records:
        raise ValueError("动态领导片段未解析到有效人物")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
