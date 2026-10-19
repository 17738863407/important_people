from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2604",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_commerce_jpage_datastore_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML内嵌JPage数据",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "collector": "raw_http",
    "parser": "page_lanzhou_commerce_jpage_datastore_v1",
    "leader_region_selector": "div[id='114707'] script[type='text/xml'] record",
    "name_selector": "record CDATA p中党组字段前姓名",
    "duty_selector": "record CDATA p中从党组字段开始的原始职务",
    "detail_link_selector": "record CDATA a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "list_item_link",
        "detail_link_selector": "record CDATA a[href]",
        "max_detail_links": 30,
    },
    "risk_flag": "historical_script_hardcoded_people_and_misclassified_hidden_visitcount_iframe",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div[id='114707'] script[type='text/xml']",
            "row_selector": "record CDATA",
        },
        "api": {
            "enabled": False,
            "reason": "当前原始HTTP页面的JPage datastore已内嵌完整领导列表及可验证详情链接",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    return re.sub(r"\s*([、，。；：])\s*", r"\1", cleaned)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按JPage datastore的record顺序动态解析姓名、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="114707")
    datastore = (
        container.find("script", attrs={"type": "text/xml"})
        if container is not None
        else None
    )
    if datastore is None or not datastore.string:
        return []

    datastore_soup = BeautifulSoup(str(datastore.string), "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for record in datastore_soup.find_all("record"):
        fragment = BeautifulSoup(str(record.string or ""), "html.parser")
        paragraph = fragment.find("p")
        link = fragment.find("a", href=True)
        if paragraph is None:
            continue
        text = normalize_space(paragraph.get_text(" ", strip=True))
        marker_index = text.find("党组")
        if marker_index <= 0:
            continue
        name = re.sub(r"\s+", "", text[:marker_index])
        duty = normalize_space(text[marker_index:])
        if (
            not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name)
            or not duty
            or name in seen_names
        ):
            continue
        seen_names.add(name)
        detail_url = urljoin(final_url, str(link.get("href", ""))) if link else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "原始HTTP页面div#114707内JPage datastore record；按record顺序以党组字段为边界拆分姓名和原始职务",
            }
        )
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
