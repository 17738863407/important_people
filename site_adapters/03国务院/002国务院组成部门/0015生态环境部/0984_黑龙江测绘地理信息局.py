from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0984",
    "page_type": "人物列表完整页",
    "structure_group": "hlsm_leader_nav_links_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".leader-nav-body ul",
    "name_selector": "li a开头中文姓名",
    "duty_selector": "li a中姓名后文本",
    "detail_link_selector": "li a[href]",
    "detail_strategy": {"required": False, "mode": "list_links"},
    "risk_flag": "规则入口本身为首人详情页，页面另含重要活动新闻链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(text: str) -> str:
    """清理网页排版空白。"""
    return re.sub(r"\s+", " ", text.replace("\u3000", " ").replace("\xa0", " ")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导导航名单顺序提取姓名、职务与人物链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    entry_url = urldefrag(urljoin(final_url, ""))[0].rstrip("/")
    records: list[PersonRecord] = []
    for link in soup.select(".leader-nav-body ul li a[href]"):
        text = _clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"(?P<name>[\u4e00-\u9fff·]{2,5})\s+(?P<duty>.+)", text)
        if match is None:
            continue
        name = match.group("name")
        duty = _clean_text(match.group("duty"))
        candidate = urldefrag(urljoin(final_url, str(link.get("href") or "")))[0]
        detail_url = "" if candidate.rstrip("/") == entry_url else candidate
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=detail_url,
                evidence=duty,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="leader-nav-body列表链接中的姓名和职务",
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
