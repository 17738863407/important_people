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


PAGE_RULE = {
    "rule_id": "1480",
    "domain": "lyj.jiangsu.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangsu_forestry_inline_xml_leader_records_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "inline_xml_records",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_forestry_inline_xml_leader_records_v2",
    "detail_strategy": {"required": False, "mode": "inline_with_verified_links"},
    "risk_flag": "旧画像误标iframe；领导卡片位于#373427 text/xml脚本CDATA；职责节点必须排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_name(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按内联XML record顺序读取领导姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="373427")
    payload_node = container.find("script", {"type": "text/xml"}) if container else None
    payload = str(payload_node.string or payload_node.get_text() or "") if payload_node else ""
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for fragment in re.findall(r"<!\[CDATA\[(.*?)\]\]>", payload, flags=re.DOTALL):
        card = BeautifulSoup(fragment, "html.parser").select_one(".leader_listcon")
        if card is None:
            continue
        link = card.select_one(".list_right h6 a[href]")
        duty_node = card.select_one(".leader_zw")
        if link is None or duty_node is None:
            continue
        name = compact_name(link.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True)).strip("，,；;。 ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": urljoin(final_url, str(link.get("href", ""))),
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；source=#373427 script[type=text/xml] CDATA record；"
                    "row=.leader_listcon；fields=h6 a+.leader_zw；"
                    "detail=h6 a[href]；exclude=.leader_fggz"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
