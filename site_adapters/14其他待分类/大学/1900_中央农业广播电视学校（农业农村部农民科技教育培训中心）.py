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


def clean_text(value: str) -> str:
    """压缩列表项中的全角空格、不换行空格和连续空白。"""
    return " ".join(
        str(value or "").replace("\u3000", " ").replace("\xa0", " ").split()
    )


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """解析单位领导正文内的“姓名 职务”列表。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；"
        "leader=.content .text .TRS_Editor ul > li；"
        "name=列表项开头中文姓名；duty=姓名后剩余原文；detail=none"
    )

    for item in soup.select(".content .text .TRS_Editor ul > li"):
        text = clean_text(item.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fa5·]{2,8})\s+(.+)", text)
        if match is None:
            continue
        name = match.group(1)
        duty = clean_text(match.group(2))
        if not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_ngx_current_leader_list_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1900",
    "domain": "www.ngx.net.cn",
    "page_type": "人物列表完整页",
    "structure_group": "ngx_current_leader_list",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_ngx_current_leader_list_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "HTTP初始响应无效，online需进入Playwright；禁止使用body全文弱结构解析以免混入导航和页脚",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "浏览器渲染DOM的最小正文列表直接包含姓名和职务",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "online_verified_20260806",
            "behavior_changed": True,
        },
    },
}


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
