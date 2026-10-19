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
    """压缩当前人物简介中的连续空白。"""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按目录顺序解析中央民族大学现任领导简介。"""
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=section.n_xrld dd a[href]；"
        "name=h5；duty=当前链接内完整现任句；detail=当前a[href]"
    )

    for link in soup.select("section.n_xrld dd a[href]"):
        name_node = link.select_one("h5")
        name = re.sub(
            r"\s+",
            "",
            name_node.get_text(" ", strip=True) if name_node else "",
        )
        text = clean_text(link.get_text(" ", strip=True))
        current_duty_match = re.search(r"现任[^。]*。", text)
        if (
            not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name)
            or current_duty_match is None
            or name in seen
        ):
            continue

        evidence = clean_text(current_duty_match.group(0))
        duty = evidence.removeprefix("现任").removesuffix("。")
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_muc_current_leader_profiles_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "1705",
    "domain": "www.muc.edu.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "muc_current_leader_profiles",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_muc_current_leader_profiles_v2",
    "detail_strategy": {
        "required": False,
        "mode": "list_dynamic_links",
        "detail_link_selector": "section.n_xrld dd a[href]",
    },
    "risk_flag": "页面模板含浏览器版本过低提示，online会误判无效；使用raw_http并只在当前人物链接内提取现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "原始静态HTML直接包含姓名、现任句和独立人物链接",
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
