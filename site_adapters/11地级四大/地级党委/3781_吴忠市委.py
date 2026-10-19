from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3781",
    "domain": "www.wuzhong.gov.cn",
    "page_type": "同页四套班子标签列表",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_wuzhong_party_leaders_v1",
    "leader_region_selector": ".Ld-option1-nav",
    "name_selector": ".ld-name",
    "duty_selector": ".ld-position",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "市委领导", "end_anchor": "人大领导", "include_selectors": [".Ld-option1-nav"], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "人物详情由docid脚本切换且无独立可验证链接，详情页留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理页面排版空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\u00a0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """仅解析标题为市委领导的导航面板。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(".ldzc-con-left")
    region = next((item for item in regions if clean_text((item.select_one(".ldzc-con-left-title") or item).get_text(" ", strip=True)).startswith("市委领导")), None)
    if not region:
        return []
    rows: list[dict[str, str]] = []
    for item in region.select("li"):
        name_node = item.select_one(".ld-name")
        duty_node = item.select_one(".ld-position")
        if not name_node or not duty_node:
            continue
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
        duty = clean_text(duty_node.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
            continue
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", ""))})
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
