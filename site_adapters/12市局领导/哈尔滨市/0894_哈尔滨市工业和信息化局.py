from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0894",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_detail_info_person_heading",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "#detailContent p",
    "duty_selector": "#detailContent p",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "只解析完整匹配姓名加明确职务的正文标题段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select("#detailContent p"):
        text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", paragraph.get_text("", strip=True))
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff·]{2,8}?)(?P<duty>党组书记、局长|党组成员、副局长|[一二三四]级巡视员)",
            text,
        )
        if not match:
            continue
        name = match.group("name")
        duty = match.group("duty")
        rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "",
                     "selector_summary": "#detailContent完整人物标题段落姓名及原始职务"})
    if not rows:
        raise ValueError("领导信息正文未发现可验证的人物标题段落")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
