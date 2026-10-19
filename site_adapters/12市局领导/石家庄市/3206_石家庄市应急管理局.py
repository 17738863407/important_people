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
    "rule_id": "3206",
    "page_type": "人物列表完整页",
    "structure_group": "shijiazhuang_emergency_leadership_article",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "shijiazhuang_emergency_column_current_article_v2",
    "leader_region_selector": "#conN",
    "name_selector": "#conN",
    "duty_selector": "#conN",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "官网当前领导信息文章；正文以连续空白分隔姓名和职务",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅合并网页排版空白，不改写字段语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按当前领导文章的正文换行顺序解析姓名职务。"""
    del final_url
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    regions = soup.select(page_rule["leader_region_selector"])
    if len(regions) != 1:
        raise RuntimeError(f"当前领导正文命中数量异常：{len(regions)}")

    records: list[object] = []
    seen_names: set[str] = set()
    for raw_line in regions[0].get_text("\n", strip=True).splitlines():
        line_match = re.fullmatch(
            r"\s*(?P<name>[一-鿿·\s\xa0]{2,20}?)[\s\xa0]{4,}(?P<duty>\S.*?)\s*",
            raw_line,
        )
        if not line_match:
            continue
        name = re.sub(r"\s+", "", line_match.group("name"))
        duty = _clean_text(line_match.group("duty"))
        if not re.fullmatch(r"[一-鿿·]{2,8}", name) or name in seen_names or not duty:
            raise RuntimeError(f"当前领导行姓名职务异常：{_clean_text(raw_line)}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url="",
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("当前领导正文未解析到姓名职务行")
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
