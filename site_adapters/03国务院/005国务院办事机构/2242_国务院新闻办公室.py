from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2242",
    "page_type": "人物卡片页",
    "structure_group": "scio_director_profile_card_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_scio_director_profile_card_v1",
    "leader_region_selector": ".director .jjg",
    "name_selector": ".jjgbg a[href] .leader-name",
    "duty_selector": ".rightcon .trs_editor_view p",
    "detail_link_selector": ".jjgbg > a[href]",
    "detail_strategy": {"required": False, "mode": "card_link", "max_detail_links": 5},
    "risk_flag": "入口HTTP先返回521；仅解析主任卡片，排除隐藏讲话和活动区域",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """只清理页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析本办介绍页中唯一可见主任卡片。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []
    name_node = region.select_one(".jjgbg a[href] .leader-name")
    link_node = region.select_one(".jjgbg > a[href]")
    name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or link_node is None:
        return []
    biography = clean_text(
        " ".join(node.get_text(" ", strip=True) for node in region.select(".rightcon .trs_editor_view p"))
    )
    match = re.search(r"现任[^。]*。", biography)
    if match is None:
        return []
    entry_url = str(page_rule.get("url") or "") or final_url
    evidence = match.group(0).removeprefix("现任").removesuffix("。").strip()
    return [
        {
            "organization": str(page_rule.get("organization") or ""),
            "url": entry_url,
            "name": name,
            "duty": evidence,
            "detail_url": urljoin(final_url or entry_url, str(link_node.get("href") or "")),
            "evidence": evidence,
            "confidence": "high",
            "parser": str(page_rule.get("parser") or ""),
            "selector_summary": (
                ".director .jjg；name=.jjgbg .leader-name；"
                "evidence=.rightcon .trs_editor_view p完整现任句；detail=.jjgbg > a[href]"
            ),
        }
    ]


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
