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
    "rule_id": "4283", "page_type": "市委领导目录", "structure_group": "赤峰市委领导目录卡片", "load_mode": "静态HTML直出", "extract_mode": "list_detail", "parser": "page_inline_chifeng_party_leaders_v1", "leader_region_selector": "市委领导目录 .qbldjs", "name_selector": ".qbldjs .mczw a.ldxm", "duty_selector": ".qbldjs .mczw a:not(.ldxm)", "detail_link_selector": ".qbldjs .mczw a.ldxm[href]", "detail_strategy": {"required": True, "mode": "list_link"}, "risk_flag": "入口页混有市政府领导摘要；市委脚本仅读取“查看更多领导”对应的市委领导目录。", "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """动态定位市委领导目录，并按卡片顺序读取姓名、职务和详情。"""
    from bs4 import BeautifulSoup
    import requests
    soup = BeautifulSoup(html, "html.parser")
    directory_link = next((a.get("href") for a in soup.select(".gdld a[href]") if "zzllmsswld" in a.get("href", "") and a.get("href", "").endswith("/")), "")
    if not directory_link:
        return []
    directory_url = urljoin(final_url or str(page_rule["url"]), directory_link)
    session = requests.Session(); session.trust_env = False; session.headers["User-Agent"] = "Mozilla/5.0"
    try:
        response = session.get(directory_url, timeout=20); response.raise_for_status()
    except requests.RequestException:
        return []
    response.encoding = response.apparent_encoding or "utf-8"
    directory = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    for card in directory.select(".qbldjs"):
        name_link = card.select_one(".mczw a.ldxm[href]")
        duty_link = card.select_one(".mczw a:not(.ldxm)")
        if not name_link or not duty_link:
            continue
        name = re.sub(r"\s+", "", name_link.get_text(" ", strip=True))
        duty = re.sub(r"\s+", "", duty_link.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": urljoin(directory_url, name_link["href"]), "parser": page_rule["parser"], "selector_summary": "市委领导目录卡片"})
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
