from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0891",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_detail_info_paragraph_start",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "正文末尾含AB角说明，解析器仅接受各人物段落开头姓名职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select("#detailContent p"):
        text = paragraph.get_text("", strip=True).replace("\u3000", " ")
        match = re.match(
            r"^(?P<name>[\u4e00-\u9fff·]{2,4}?)(?P<duty>(?:正|副)?局长|[一二三四]级巡视员|[一二三四]级调研员)(?P<tail>.*)$",
            text,
        )
        if not match:
            continue
        tail = match.group("tail")
        if re.match(r"^[\s\u2000-\u200b]*(?:负责|分管|协助|主持)", tail) is None:
            continue
        name = match.group("name")
        duty = match.group("duty")
        evidence = duty
        rows.append({"name": name, "duty": duty, "evidence": evidence, "detail_url": "",
                     "selector_summary": "#detailContent人物段落原始开头姓名职务"})
    if not rows:
        raise ValueError("领导信息正文未发现可验证的人物段落")
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
