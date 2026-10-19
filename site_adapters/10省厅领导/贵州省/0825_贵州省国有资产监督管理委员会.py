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
    """压缩网页排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(value: str) -> str:
    """去除姓名中的网页排版空格。"""
    return clean_text(value).replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按委党委班子目录顺序在线请求详情并读取职务强字段。"""
    import requests

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, link in enumerate(soup.select(".ldleft .er a[href][title]"), start=1):
        name = clean_name(str(link.get("title") or link.get_text(" ", strip=True)))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        response = session.get(detail_url, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        duty_node = detail_soup.select_one(".ldright .ldjl")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        evidence = re.sub(r"<(?:兼|挂职)>", "", duty).strip()
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": response.url,
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_inline_guizhou_sasac_party_detail_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0825",
    "page_type": "人物列表完整页",
    "structure_group": "贵州国资委党委班子目录转详情",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_guizhou_sasac_party_detail_v2",
    "leader_region_selector": ".ldleft .er",
    "name_selector": ".ldleft .er a[title]",
    "duty_selector": "详情页.ldright .ldjl",
    "detail_link_selector": ".ldleft .er a[href][title]",
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
    },
    "risk_flag": "页面含其他班子与页脚链接，入口严格限定委党委班子左侧目录，详情只取.ldjl职务字段",
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
