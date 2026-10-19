from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0777",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_gxs_xml_leader_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "iframe嵌入",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_gxs_xml_leader_links_v1",
    "leader_region_selector": "div[id='22438']中的当前领导成员数据",
    "name_selector": "领导成员链接文本末尾姓名",
    "duty_selector": "领导成员链接文本中的姓名前职务",
    "detail_link_selector": "领导成员链接a[href*='art_5346_']",
    "detail_strategy": {
        "required": False,
        "mode": "dynamic_list_links",
        "detail_link_selector": "a[href*='art_5346_']",
        "max_detail_links": 20,
    },
    "risk_flag": "栏目数据位于text/xml脚本中，链接文本为职务加姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    return re.sub(
        r"[\s\u3000\xa0]+",
        " ",
        str(text or ""),
    ).strip()


def extract_links(html: str, final_url: str) -> list[tuple[str, str]]:
    """兼容渲染DOM与原始text/xml数据，保持栏目记录顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for link in soup.select("div[id='22438'] li a[href*='art_5346_']"):
        candidates.append(
            (
                normalize_space(link.get_text(" ", strip=True)),
                urljoin(final_url, str(link.get("href", "")).strip()),
            )
        )

    if not candidates:
        pattern = re.compile(
            r"<a\s+href=[\"']([^\"']*art_5346_[^\"']+)[\"'][^>]*>(.*?)</a>",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            text = normalize_space(BeautifulSoup(match.group(2), "html.parser").get_text(" ", strip=True))
            candidates.append((text, urljoin(final_url, match.group(1).strip())))

    entries: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for text, detail_url in candidates:
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        entries.append((text, detail_url))
    return entries


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从领导成员栏目按网页顺序拆分原始职务和姓名。"""
    entries = extract_links(html, final_url)
    rows: list[dict[str, str]] = []
    for text, detail_url in entries:
        match = re.fullmatch(
            r"(?P<duty>.+?(?:主任|副主任))\s+(?P<name>[\u4e00-\u9fff·]{2,8})",
            text,
        )
        if not match:
            continue
        rows.append(
            {
                "name": match.group("name"),
                "duty": match.group("duty"),
                "evidence": match.group("duty"),
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "div[id='22438']栏目记录顺序；链接文本按末尾姓名拆分职务",
            }
        )
    if not rows:
        raise RuntimeError("当前在线领导成员栏目未发现可验证的职务姓名记录")
    if len(rows) != len(entries):
        raise RuntimeError("当前在线领导成员栏目存在无法可靠拆分的记录")
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
