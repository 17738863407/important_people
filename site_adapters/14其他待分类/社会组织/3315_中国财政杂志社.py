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


def clean_text(value: str) -> str:
    """压缩领导简介文本中的全角空格和连续空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """在领导简介链接内部提取姓名、现任句和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；"
        "leader=.ldcon .kuai .ldauthor a[href]；"
        "name=简介开头逗号前；duty=当前链接内现任句；detail=当前a[href]"
    )

    for link in soup.select(".ldcon .kuai .ldauthor a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        name_match = re.match(r"^([\u4e00-\u9fa5·]{2,8})，", text)
        current_duty_match = re.search(r"现任[^。]*。", text)
        if name_match is None or current_duty_match is None:
            continue

        name = name_match.group(1)
        if name in seen:
            continue
        evidence = clean_text(current_duty_match.group(0))
        duty = evidence.removeprefix("现任").removesuffix("。")
        href = clean_text(str(link.get("href") or ""))
        detail_url = urljoin(base_url, href) if href else ""

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_finance_magazine_leaders_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3315",
    "domain": "www.zgcznet.com",
    "page_type": "多人物详情合并页",
    "structure_group": "finance_magazine_leader_intro",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_finance_magazine_leaders_v2",
    "detail_strategy": {
        "required": False,
        "mode": "list_dynamic_links",
        "detail_link_selector": ".ldauthor a[href]",
    },
    "risk_flag": "online会误跟随站内搜索脚本；同一ldcon还含处室设置，必须以简介开头姓名和当前链接内现任句双重限定",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "原始静态HTML直接包含领导简介和独立详情链接",
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
