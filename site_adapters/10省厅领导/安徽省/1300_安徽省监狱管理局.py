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
    "rule_id": "1300", "page_type": "人物列表完整页", "structure_group": "安徽省监狱管理局领导列表",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "raw_http",
    "extract_mode": "list_direct", "collector": "static_http", "parser": "page_anhui_prison_public_list_title_split_v2",
    "leader_region_selector": ".xxgk_nav_list", "name_selector": "a.title冒号前文本",
    "duty_selector": "a.title冒号后文本", "detail_link_selector": "a.title[href]",
    "risk_flag": "requests丢失catId并混入非人物公开信息", "confidence": "high",
    "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for link in soup.select(".xxgk_nav_list li a.title[href]"):
        parts = re.split(r"[:：]", clean_text(link.get_text(" ", strip=True)), maxsplit=1)
        if len(parts) != 2:
            continue
        name, duty = re.sub(r"\s+", "", parts[0]), clean_text(parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        rows.append({"organization": page_rule["organization"], "url": page_rule["url"], "name": name,
                     "duty": duty, "detail_url": urljoin(final_url, str(link.get("href") or "")),
                     "evidence": duty, "confidence": "high", "parser": "page_anhui_prison_public_list_title_split_v2",
                     "selector_summary": "strategy=custom_parse_page；item=.xxgk_nav_list li a.title[href]；split=首个中文冒号"})
    if not rows:
        raise RuntimeError("安徽省监狱管理局领导列表未抽取到人物")
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
