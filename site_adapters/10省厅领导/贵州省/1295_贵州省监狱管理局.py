from __future__ import annotations

import html as html_lib
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


def normalize_space(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """姓名内部不保留排版空白。"""
    return normalize_space(value).replace(" ", "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析领导目录内联脚本动态生成的人物卡片字段。"""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.select_one("ul.ldzc script")
    script_text = str(script.string or "") if script else ""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, segment in enumerate(re.split(r"(?=\bvar\s+src\s*=)", script_text), start=1):
        url_match = re.search(r'var\s+src\s*=\s*"(?P<detail>https?://[^"]+)"', segment)
        field_match = re.search(r"<p>(?P<name>[^<]+)</p><span>(?P<duty>[^<]+)</span>", segment)
        if not url_match or not field_match:
            continue
        name = clean_name(html_lib.unescape(field_match.group("name")))
        duty = normalize_space(html_lib.unescape(field_match.group("duty"))).strip(" ：:，。")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": url_match.group("detail"),
                "source_order": str(source_order),
                "confidence": "high" if duty else "medium",
                "parser": "page_guizhou_prison_inline_cards_v2",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1295",
    "page_type": "人物列表完整页",
    "structure_group": "贵州监狱局内联脚本领导卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_guizhou_prison_inline_cards_v2",
    "leader_region_selector": "ul.ldzc script",
    "name_selector": "内联卡片p字段",
    "duty_selector": "内联卡片span字段",
    "detail_link_selector": "内联脚本var src字段",
    "detail_strategy": {
        "required": False,
        "mode": "inline_script_link_only",
        "detail_collector_type": "none",
    },
    "risk_flag": "ul.ldzc原始HTML为空，人物卡片由当前页内联脚本按顺序生成，需解析同一脚本块的src、p、span字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
