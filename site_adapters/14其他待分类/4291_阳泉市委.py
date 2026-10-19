from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4291", "page_type": "市委领导分组照片卡片", "structure_group": "阳泉市委领导书记副书记常委列表", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_yangquan_party_leaders_v1", "leader_region_selector": ".sw-leader-left", "name_selector": ".sw-leader-left li p a[href]", "duty_selector": ".sw-leader-left li > span", "detail_link_selector": ".sw-leader-left li p a[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "右侧为活动新闻，人物仅取左侧书记、副书记、常委照片卡片。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市委领导分组及照片卡片 DOM 顺序提取人员。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    for group in soup.select(".sw-leader-left > li"):
        role_node = group.select_one(":scope > span")
        if not role_node:
            continue
        duty = "市委" + re.sub(r"[\s:：]", "", role_node.get_text(" ", strip=True))
        for link in group.select("p a[href]"):
            name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, link["href"]), "parser": page_rule["parser"], "selector_summary": "市委领导分组照片卡片"})
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
