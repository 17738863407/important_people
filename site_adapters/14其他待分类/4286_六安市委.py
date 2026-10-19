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
    "rule_id": "4286", "page_type": "动态JS领导目录", "structure_group": "六安市委领导三类动态链接列表", "load_mode": "静态HTML与可复现JS片段", "extract_mode": "api_direct", "parser": "page_inline_luan_party_leaders_v1", "leader_region_selector": ".ld-sj, .ld_fsj, .ld_cw", "name_selector": "各分类JS片段中的 a[title]", "duty_selector": "入口页分类职务", "detail_link_selector": "各分类JS片段中的 a[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "姓名列表由三份JS片段加载；详情页当前返回521，不能据此补造未展示的完整职务。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """读取入口实际引用的动态片段并按分类、片段内顺序抽取人员。"""
    from bs4 import BeautifulSoup
    import requests
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session(); session.trust_env = False; session.headers["User-Agent"] = "Mozilla/5.0"
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    base_url = final_url or str(page_rule["url"])
    for group in soup.select(".ld-sj, .ld_fsj, .ld_cw"):
        duty_node = group.select_one(".ld-zw")
        script = group.select_one("script[src*='.js']")
        if not duty_node or not script:
            continue
        duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True))
        fragment_url = urljoin(base_url, script["src"])
        try:
            response = session.get(fragment_url, timeout=20, verify=False); response.raise_for_status()
        except requests.RequestException:
            continue
        fragment = BeautifulSoup(response.text, "html.parser")
        for link in fragment.select("a[title][href]"):
            name = re.sub(r"\s+", "", link.get("title", ""))
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
                continue
            seen.add(name)
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(base_url, link["href"]), "parser": page_rule["parser"], "selector_summary": "市委分类JS片段链接"})
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
