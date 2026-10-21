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
    "rule_id": "0590",
    "page_type": "人物列表完整页",
    "structure_group": "安徽省发改委领导列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_anhui_fgw_leader_spans_v3",
    "leader_region_selector": ".ls-ld-list",
    "name_selector": "li a[href] span.name",
    "duty_selector": "li a[href] span.pos",
    "detail_link_selector": "li a[href]",
    "risk_flag": "新入口为机构领导模板页，仅解析右侧领导列表容器。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按列表DOM顺序解析安徽省发改委领导。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select(".ls-ld-list li a[href]"):
        name_node, duty_node = link.select_one("span.name"), link.select_one("span.pos")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "").lstrip("：:")
        duty = re.sub(r"[（(]\s*兼\s*[）)]", "", duty).strip("，,、；;。 ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        rows.append({
            "organization": page_rule["organization"], "url": page_rule["url"],
            "name": name, "duty": duty,
            "detail_url": urljoin(final_url, str(link.get("href") or "")), "evidence": duty,
            "confidence": "high", "parser": "page_inline_anhui_fgw_leader_spans_v3",
            "selector_summary": "strategy=custom_parse_page；item=.ls-ld-list li a[href]；name=span.name；duty=span.pos",
        })
    if not rows:
        raise RuntimeError("安徽省发改委领导列表未抽取到人物")
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
