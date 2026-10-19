from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0094',
 'page_type': '人物列表完整页',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'online',
 'force_browser': True,
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '.Organization_con',
 'name_selector': '.Organization_con p中职务前姓名',
 'duty_selector': '.Organization_con p末尾主任/副主任/总农艺师',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': 'requests为安全拦截页；页面声明GB2312，浏览器渲染后在最小领导容器解析',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'custom_parse_page',
 'risk_note': '禁止回退到body；只解析.Organization_con内完整匹配姓名和3类职务的段落。'}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析农业农村部农产品质量安全中心领导正文。"""
    import re

    from bs4 import BeautifulSoup

    if "ÖĐĐÄÁěµĽ" in html:
        html = html.encode("cp1250", errors="ignore").decode("gb18030", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".Organization_con")
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    paragraphs = region.select("p")
    for paragraph in paragraphs:
        raw_text = re.sub(r"[\s\u3000\xa0]+", " ", paragraph.get_text(" ", strip=True)).strip()
        normalized = raw_text.replace(" ", "")
        match = re.search(r"^([\u4e00-\u9fff]{2,4}?)(总农艺师|副主任|主任)$", normalized)
        if not match:
            continue
        name = match.group(1)
        duty = match.group(2)
        if name in seen or name.endswith("领导"):
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "parser": "page_parse_page",
                "selector_summary": ".Organization_con内完整人物段",
            }
        )
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
