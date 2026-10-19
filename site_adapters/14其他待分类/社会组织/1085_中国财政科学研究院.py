from __future__ import annotations

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
    """压缩页面职务字段中的全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按页面顺序解析院长卡片及现任领导列表。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    items = list(soup.select(".yuanzhang_box"))
    items.extend(soup.select(".xrld_ul li"))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；"
        "leader=.yuanzhang_box,.xrld_ul li；"
        "name=.name_text；duty=.zhiwu_text；detail=人物块a[href]"
    )

    for item in items:
        name_node = item.select_one(".name_text")
        duty_node = item.select_one(".zhiwu_text")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not name or not duty or name in seen:
            continue

        link = item.find_parent("a", href=True) or item.select_one("a[href]")
        href = clean_text(str(link.get("href") or "")) if link else ""
        detail_url = urljoin(base_url, href) if href else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_icafs_current_leaders_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1085",
    "domain": "www.icafs.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "icafs_current_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_icafs_current_leaders_v2",
    "detail_strategy": {
        "required": False,
        "mode": "list_dynamic_links",
        "detail_link_selector": "人物块a[href]",
    },
    "risk_flag": "院长与其他现任领导使用两种并列结构，必须依次合并并保持页面顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "当前静态HTML直接包含三名现任领导及详情链接",
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
