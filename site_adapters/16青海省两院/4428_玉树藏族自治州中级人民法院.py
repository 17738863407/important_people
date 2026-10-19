from __future__ import annotations

import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """核验领导之窗是否发布人物条目；空栏目必须显式进入人工复核。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".content-r")
    if region is None:
        raise RuntimeError("页面未找到领导之窗内容区域 .content-r，需人工复核页面结构")

    heading = region.select_one(".tit_brb h2, .tit_br h2, #title h2")
    heading_text = heading.get_text(" ", strip=True) if heading else ""
    if "领导之窗" not in heading_text:
        raise RuntimeError("当前栏目标题不是领导之窗，禁止从其他栏目推断人物")

    links = region.select(".list_br a[href], .list a[href]")
    if links:
        raise RuntimeError("领导之窗出现新的文章链接，现有空栏目规则需人工复核后再启用")
    raise RuntimeError("领导之窗当前未发布可验证的人物条目，需人工复核")


PAGE_RULE = {
    "rule_id": "4428",
    "domain": "yszy.qhwsfy.gov.cn",
    "page_type": "领导栏目空页",
    "structure_group": "qinghai_court_empty_leader_column",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "manual_review",
    "collector": "raw_http",
    "parser": "page_qinghai_court_empty_leader_column_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".content-r",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": ".content-r .list_br a[href], .content-r .list a[href]",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "领导之窗当前只有栏目标题且无人物条目；禁止改用公告、法院文化或院长介绍栏目补齐名单",
    "confidence": "manual_review",
    "filter_policy": "strong_no_wordlist",
    "locator": {
        "css": {
            "leader_region_selector": ".content-r",
            "heading_selector": ".tit_brb h2, .tit_br h2, #title h2",
            "detail_link_selector": ".list_br a[href], .list a[href]",
        },
        "api": {"enabled": False, "reason": "当前领导之窗静态栏目未发布人物数据"},
    },
}


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
