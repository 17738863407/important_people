from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2992",
    "page_type": "人物表格页",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "parser": "page_parse_page",
    "leader_region_selector": "table.leadtb",
    "name_selector": "table.leadtb a[href]",
    "duty_selector": ".artibody",
    "detail_link_selector": "table.leadtb a[href]",
    "detail_strategy": {"required": True, "mode": "person_name_link"},
    "risk_flag": "列表同时保留display:none历史人物；必须排除当前节点及祖先隐藏状态",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "只遍历可见leadtb并从对应详情.artibody提取完整现任句；工作分工不得作为职务依据。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析可见领导表格，并在线读取对应人物详情的现任职务句。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    def clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()

    def is_hidden(element: object) -> bool:
        for current in (element, *getattr(element, "parents", [])):
            if not hasattr(current, "attrs"):
                continue
            if current.has_attr("hidden") or clean_text(current.get("aria-hidden", "")).lower() == "true":
                return True
            style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
            if "display:none" in style or "visibility:hidden" in style:
                return True
        return False

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for table in soup.select("table.leadtb"):
        if is_hidden(table):
            continue
        link = next((node for node in table.select("a[href]") if clean_text(node.get_text(" ", strip=True))), None)
        if link is None:
            continue
        raw_label = clean_text(link.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", raw_label.split("：", 1)[0])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        detail_result = fetch_html_with_strategy(urljoin(final_url, str(link.get("href", ""))), "requests")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        title = detail_soup.title.get_text(" ", strip=True) if detail_soup.title else ""
        if name not in re.sub(r"\s+", "", title):
            raise ValueError(f"领导详情标题与列表姓名不一致：{name}")
        detail_node = detail_soup.select_one(".artibody")
        detail_text = clean_text(detail_node.get_text(" ", strip=True) if detail_node else "")
        duty_match = re.search(r"现任[^。]*。", detail_text)
        if duty_match is None:
            raise ValueError(f"领导详情缺少完整现任职务句：{name}")
        evidence = duty_match.group(0).removeprefix("现任").removesuffix("。")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_result.final_url,
                "evidence": evidence,
                "parser": "page_parse_page",
                "selector_summary": "列表=可见table.leadtb；详情=.artibody现任句",
            }
        )
    if not rows:
        raise ValueError("当前页面未发现可见领导表格")
    return rows


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
