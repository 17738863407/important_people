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
    "rule_id": "0858",
    "page_type": "人物目录详情页",
    "structure_group": "目录姓名链接与详情个人简介",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "GuangzhouCppccLeaderDetailParser_v2",
    "leader_region_selector": ".content a.title[href]",
    "detail_content_selector": ".grjj",
    "risk_flag": "职务仅在人物详情页个人简介最小容器的现任句中",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一网页排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_current_evidence(value: str) -> str:
    """删除固定现任标签和句末句号，并归一中文标点附近排版空格。"""
    evidence = re.sub(r"^现任\s*", "", _clean_text(value))
    evidence = re.sub(r"\s*([，、；：。])\s*", r"\1", evidence)
    return re.sub(r"。$", "", evidence).strip()


def _extract_current_sentence(html: str, selector: str) -> str:
    """只在当前人物简介容器内提取完整“现任……”句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(selector)
    text = _clean_text(region.get_text(" ", strip=True) if region else "")
    match = re.search(r"现任[^。]*。", text)
    return _clean_current_evidence(match.group(0)) if match else ""


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按目录DOM顺序访问人物详情页并提取现任句。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for source_order, link in enumerate(soup.select(rule["leader_region_selector"]), start=1):
        name = "".join(_clean_text(link.get_text(" ", strip=True)).split())
        href = (link.get("href") or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not detail_url or name in seen:
            continue
        detail_result = fetch_html_with_strategy(
            detail_url,
            strategy="online",
            timeout=40,
            request_attempt_offset=source_order,
        )
        evidence = _extract_current_sentence(detail_result.html, rule["detail_content_selector"])
        if not evidence:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "parser": rule["parser"],
                "selector_summary": "目录.content a.title；详情.grjj内完整现任句",
            }
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
