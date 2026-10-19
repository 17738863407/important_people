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
    "rule_id": "1157",
    "domain": "jllc.jl.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jilin_forestry_side_leaders_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jilin_forestry_side_leaders_v2",
    "detail_strategy": {"required": False, "mode": "inline_with_verified_links"},
    "risk_flag": "增强requests误跳无障碍通道；raw_http保留侧栏，首人同址详情留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def normalize_url(value: str) -> str:
    """仅用于判断入口页与详情链接是否相同。"""
    return str(value or "").strip().rstrip("/")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按侧栏顺序拆分“职务：姓名”，并纠正入口同址详情。"""
    soup = BeautifulSoup(html, "html.parser")
    basis_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".pz_SideLayer a[href]"):
        text = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)\s*[：:]\s*([\u3400-\u9fff·\s\u3000]{2,10})", text)
        if match is None:
            continue
        duty = clean_text(match.group(1)).strip("，,。 ")
        name = re.sub(r"\s+", "", clean_text(match.group(2)))
        if not duty or not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")))
        if normalize_url(detail_url) == normalize_url(basis_url):
            detail_url = ""
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": basis_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；row=.pz_SideLayer a[href]；"
                    "field=link-text duty:name；detail=blank-if-entry"
                ),
            }
        )

    return records


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
