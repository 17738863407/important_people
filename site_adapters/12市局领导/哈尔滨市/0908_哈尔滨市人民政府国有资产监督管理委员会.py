from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


PAGE_RULE = {
    "rule_id": "0908",
    "page_type": "多人物详情合并页",
    "structure_group": "harbin_image_intro_current_sentence_blocks",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "人物简介块段首逗号前",
    "duty_selector": "当前人物简介块内完整现任句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "只在当前人物直接子级简介块内提取现任句，排除后续职责分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_current_evidence(value: str) -> str:
    """删除固定现任标签和纯句末句号，保留完整任职语义。"""
    evidence = re.sub(r"^现任\s*", "", clean_text(value))
    return re.sub(r"。$", "", evidence).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#detailContent")
    if region is None:
        raise ValueError("未找到领导信息正文 #detailContent")
    rows: list[dict[str, str]] = []
    for block in (child for child in region.children if isinstance(child, Tag)):
        text = clean_text(block.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff]{2,4})[，,]", text)
        if not name_match:
            continue
        current_match = re.search(r"现任[^。]*(?:。|$)", text)
        if not current_match:
            raise ValueError(f"当前人物简介块缺少可验证的现任句：{name_match.group('name')}")
        evidence = clean_current_evidence(current_match.group(0))
        rows.append(
            {
                "name": name_match.group("name"),
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "selector_summary": "#detailContent直接子级人物简介块内现任句",
            }
        )
    if not rows:
        raise ValueError("领导信息正文未发现可验证的人物简介块")
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
