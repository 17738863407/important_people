from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4220", "page_type": "负责人公告列表", "load_mode": "静态 HTML 直出",
    "extract_mode": "list_direct", "parser": "page_inline_cma_leader_notices_v1",
    "leader_region_selector": "ul.mesgopen2", "name_selector": "ul.mesgopen2 > li > a",
    "duty_selector": "ul.mesgopen2 > li > a 的冒号前标题", "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"}, "confidence": "high",
    "filter_policy": "strong_list_structure",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """仅解析负责人列表项内“职务：姓名”公告标题，保留页面顺序。"""
    from bs4 import BeautifulSoup
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(str(page_rule["url"]), headers=headers, timeout=30, verify=False)
    response.raise_for_status()
    response.encoding = "utf-8"
    rows: list[dict] = []
    for anchor in BeautifulSoup(response.text, "html.parser").select("ul.mesgopen2 > li > a"):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        match = re.fullmatch(r"(.+?)：([\u4e00-\u9fff]{2,4})", title)
        if match:
            duty, name = match.groups()
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
