from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3459",
    "page_type": "人物列表完整页",
    "structure_group": "gx_tcm_leader_category_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".more-pages",
    "name_selector": ".more-pages a[href]",
    "duty_selector": "人物链接路径中的jz或fjz栏目",
    "detail_link_selector": ".more-pages a[href]",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时含面包屑和局长、副局长栏目链接；仅接受栏目下的短中文人物链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_name(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u200b", "")
    return re.sub(r"\s+", "", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物链接DOM顺序从稳定栏目路径确定网页原始职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    entry_url = final_url or page_rule["url"]
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".more-pages a[href]"):
        name = _clean_name(link.get_text(" ", strip=True))
        if name in {"局长", "副局长"} or re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            continue
        href = str(link.get("href", ""))
        path = urljoin(entry_url, href)
        if "/ldxx/jz/" in path:
            duty = "局长"
        elif "/ldxx/fjz/" in path:
            duty = "副局长"
        else:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": path,
            }
        )

    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
