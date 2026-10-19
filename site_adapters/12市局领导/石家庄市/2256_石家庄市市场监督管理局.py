from __future__ import annotations

import sys
import re
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2256',
 'page_type': '人物列表完整页',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '#conN',
 'risk_flag': '',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'risk_note': '正文按人物职务行与分工行交替排列；职务使用楷体，分工使用仿宋，个别div存在异常嵌套。'}


def _make_record(page_rule: dict, name: str, duty: str) -> object:
    from crawler_core.models import PersonRecord

    return PersonRecord(
        organization=page_rule["organization"],
        url=page_rule["url"],
        name=name,
        duty=duty,
        detail_url="",
        evidence=duty,
        confidence="high",
        parser="page_parse_page",
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """解析石家庄市市场监督管理局领导分工正文，排除分管段落。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#conN")
    if region is None:
        return []

    heading_parts: dict[int, list[str]] = {}
    for font in region.select('font[face*="楷体"]'):
        block = font.find_parent("div")
        if block is None:
            continue
        heading_parts.setdefault(id(block), []).append(font.get_text(" ", strip=True))

    records = []
    for parts in heading_parts.values():
        text = re.sub(r"[\s\u00a0]+", "", "".join(parts))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,6})[：:](.+)", text)
        if match is None:
            continue
        name, duty = match.groups()
        records.append(_make_record(page_rule, name, duty))
    return records


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
