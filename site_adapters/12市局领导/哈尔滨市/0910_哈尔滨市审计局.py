from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0910",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_standalone_name_following_duty_paragraph",
    "reuse_scope": "page_structure",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent",
    "name_selector": "独立姓名段落",
    "duty_selector": "姓名后的首个非空段落首句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "只绑定独立姓名段落后的首句职务，排除主持、协助和分管内容",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select("#detailContent p")
    rows: list[dict[str, str]] = []
    for index, paragraph in enumerate(paragraphs):
        name = clean_text(paragraph.get_text("", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        duty_text = ""
        for following in paragraphs[index + 1 :]:
            following_text = clean_text(following.get_text(" ", strip=True))
            if following_text:
                duty_text = following_text
                break
        duty_match = re.match(r"(?P<duty>[^。；]+)[。；]", duty_text)
        if not duty_match:
            raise ValueError(f"独立姓名段落后未取得可靠原始职务：{name}")
        duty = clean_text(duty_match.group("duty"))
        if re.match(r"^(?:主持|负责|协助|分管)", duty):
            raise ValueError(f"独立姓名段落后的首句不是职务：{name}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "#detailContent独立姓名段落及后续首个非空段落首句",
            }
        )
    if not rows:
        raise ValueError("领导信息正文未发现可验证的姓名职务段落")
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
