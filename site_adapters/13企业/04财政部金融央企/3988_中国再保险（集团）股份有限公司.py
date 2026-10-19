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
    "rule_id": "3988", "domain": "www.chinare.com.cn", "page_type": "公司领导卡片及详情链接",
    "structure_group": "chinare_board_cards", "reuse_scope": "chinare_group_leaders",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_chinare_board_cards_v1", "leader_region_selector": ".Board",
    "name_selector": ".Boardul > li a[istitle='true']", "duty_selector": ".Boardul > li div a[title]",
    "content_scope": {"include_selectors": [".Board"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "dynamic_links"},
    "risk_flag": "部分职务被拆成相邻多个链接，须在单张卡内按DOM顺序拼接并保留人物详情链接",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"record_selector": ".Boardul > li", "name_selector": "a[istitle='true']", "field_selector": "div a[title]"}},
}


def normalize_text(value: str) -> str:
    """清理卡片字段中的纯排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "").strip("。；; ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐卡提取姓名链接，并按DOM顺序拼接被拆分的职务片段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".Boardul > li"):
        name_anchor = card.select_one("a[istitle='true'][href]")
        name = normalize_text(name_anchor.get_text(" ", strip=True)) if name_anchor else ""
        duty_parts = []
        for anchor in card.select("div > a[title]"):
            text = normalize_text(anchor.get_text(" ", strip=True))
            if text and text != name:
                duty_parts.append(text)
        duty = "".join(duty_parts).strip("。；; ")
        href = str(name_anchor.get("href", "")).strip() if name_anchor else ""
        detail_url = urljoin(final_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": detail_url,
            "parser": str(page_rule.get("parser", "")), "selector_summary": "公司领导卡姓名链接及同卡相邻职务链接片段",
        })
    if not rows:
        raise RuntimeError("公司领导卡片未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
