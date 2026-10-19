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
    "rule_id": "2532",
    "page_type": "职务分组名单页",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "parser": "page_parse_page",
    "leader_region_selector": ".con06",
    "name_selector": ".con06 p a.td18s1",
    "duty_selector": ".con06 p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物锚点href为#，不是详情页；不得把入口或锚点作为详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "只解析院领导正文.con06中职务：姓名段落，姓名锚点#不输出为详情页。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析院领导正文中逐段列出的职务与姓名。"""
    import re

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select(".con06 p"):
        name_node = paragraph.select_one("a.td18s1")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
        raw_text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
        duty = re.sub(r"[：:]\s*" + re.escape(re.sub(r"\s+", " ", name_node.get_text(" ", strip=True)).strip()) + r"\s*$", "", raw_text).strip()
        duty = duty.rstrip("：:").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            raise ValueError(f"院领导职务姓名段落结构无法验证：{raw_text[:80]}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "page_parse_page",
                "selector_summary": "院领导正文=.con06；人物段=.con06 p；姓名=a.td18s1",
            }
        )
    if not rows:
        raise ValueError("院领导正文未发现职务姓名段落")
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
