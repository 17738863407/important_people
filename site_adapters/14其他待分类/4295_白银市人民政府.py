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
    "rule_id": "4295", "page_type": "市政府领导分组卡片", "structure_group": "白银市领导之窗市政府容器", "load_mode": "静态HTML直出", "extract_mode": "list_direct", "parser": "page_inline_baiyin_government_leaders_v1", "leader_region_selector": "含代市长简介的 .ldConList", "name_selector": "市政府容器姓名标题和分组链接", "duty_selector": "市长现任句与相邻分组标题", "detail_link_selector": "市政府容器人物链接", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "同页并列人大、市政府、政协三个领导容器，必须通过代市长简介锚定市政府容器。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按市政府领导容器的主卡片和分组卡片顺序提取字段。"""
    from bs4 import BeautifulSoup
    import requests
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one(".ldConList"):
        session = requests.Session()
        session.trust_env = False
        session.headers["User-Agent"] = "Mozilla/5.0"
        try:
            response = session.get(str(page_rule["url"]), timeout=20, verify=False)
            response.raise_for_status()
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
        except requests.RequestException:
            return []
    container = next((box for box in soup.select(".ldConList") if box.select_one(".ldConLtop h2") and "市长" in box.select_one(".ldConLtop h2").get_text()), None)
    if not container:
        return []
    rows: list[dict[str, str]] = []
    base_url = final_url or str(page_rule["url"])
    main = container.select_one(".ldConLtop")
    if main:
        name_node, intro_node, link = main.select_one("h1"), main.select_one("p"), main.select_one("a[href]")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        intro = re.sub(r"\s+", "", intro_node.get_text(" ", strip=True)) if intro_node else ""
        match = re.search(r"现任(.+?)。", intro)
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and match and link:
            duty = match.group(1)
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, link["href"]), "parser": page_rule["parser"], "selector_summary": "市政府主领导简介现任句"})
    current_duty = ""
    for node in container.select(".ldConR h1, .ldConR a[href]"):
        if node.name == "h1":
            current_duty = re.sub(r"\s+", "", node.get_text(" ", strip=True))
            continue
        name = re.sub(r"\s+", "", node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and current_duty:
            rows.append({"name": name, "duty": current_duty, "evidence": current_duty, "detail_url": urljoin(base_url, node["href"]), "parser": page_rule["parser"], "selector_summary": "市政府领导分组卡片"})
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
