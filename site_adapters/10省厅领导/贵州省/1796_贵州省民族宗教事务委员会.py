from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """确定性清理详情简介中的排版空白。"""
    text = re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    text = re.sub(r"\s*([、，,；;：:。（）()])\s*", r"\1", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text


def extract_current_sentence(detail_html: str) -> str:
    """只在详情人物区的简介节点中提取完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for node in soup.select(".ldzc_right .TRS_UEDITOR"):
        text = clean_text(node.get_text(" ", strip=True))
        match = re.search(r"现任[^。]*。", text)
        if match:
            evidence = re.sub(r"^现任\s*", "", clean_text(match.group(0)))
            return re.sub(r"。\s*$", "", evidence)
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导之窗目录顺序在线请求详情并提取完整现任句。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select('.scroll_main1 a[href*="/ldzc1/"]'), start=1):
        name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        evidence = extract_current_sentence(response.text)
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if evidence else "medium",
                "parser": "guizhou_mzw_leader_detail_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1796",
    "page_type": "人物列表完整页",
    "structure_group": "贵州民宗委领导目录转详情简介",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "guizhou_mzw_leader_detail_v2",
    "leader_region_selector": ".scroll_main1",
    "name_selector": '.scroll_main1 a[href*="/ldzc1/"]',
    "duty_selector": ".ldzc_right .TRS_UEDITOR内完整现任句",
    "detail_link_selector": '.scroll_main1 a[href*="/ldzc1/"]',
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "详情含分工与简介两个编辑器节点，须仅接受含现任句的当前人物简介节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
