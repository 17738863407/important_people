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


def clean_text(value: str) -> str:
    """压缩网页排版空白，并合并中文词组中的换行空格。"""
    text = re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return re.sub(r"\s*([，、；：])\s*", r"\1", text)


def parse_detail_page(html: str, expected_name: str, detail_url: str) -> dict[str, str] | None:
    """在当前人物详情容器内提取姓名和现任职务，排除职责分工。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".details .introduce")
    if content is None:
        return None
    text = clean_text(content.get_text(" ", strip=True))
    name_match = re.match(r"(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
    duty_match = re.search(r"(?P<evidence>现任.*?)(?=[，；。](?:主持|负责|分管|协助|联系)|$)", text)
    if name_match is None or duty_match is None or name_match.group("name") != expected_name:
        return None
    evidence = duty_match.group("evidence").strip("，；。 ").removeprefix("现任")
    if not evidence:
        return None
    return {"name": expected_name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
            "confidence": "high", "parser": "page_inline_shanxi_prison_list_detail_v2",
            "selector_summary": "list=.detaillist .columnlist li a；detail=.details .introduce；duty=现任短语并排除职责"}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录顺序动态抓取并解析每个人物详情页。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in soup.select(".detaillist .columnlist li a[href]")[:20]:
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True) or str(link.get("title") or "")))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not detail_url or name in seen:
            continue
        detail_html = fetch_html_with_strategy(detail_url, "raw_http").html
        row = parse_detail_page(detail_html, name, detail_url)
        if row is None:
            continue
        seen.add(name)
        rows.append(row)
    return rows


PAGE_RULE = {
    "rule_id": "1320", "page_type": "人物目录详情页", "structure_group": "shanxi_prison_list_detail", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_to_detail", "collector": "static_http", "parser": "page_inline_shanxi_prison_list_detail_v2",
    "leader_region_selector": ".detaillist .columnlist li a[href]", "name_selector": ".detaillist .columnlist li a", "duty_selector": ".details .introduce current-duty phrase", "detail_link_selector": ".detaillist .columnlist li a[href]",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".detaillist .columnlist", ".details .introduce"], "exclude_selectors": []},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_collector_type": "raw_http", "detail_link_selector": ".detaillist .columnlist li a[href]", "detail_name_selector": ".details .introduce", "detail_duty_selector": ".details .introduce", "detail_content_selector": ".details .introduce", "max_detail_links": 20},
    "risk_flag": "详情正文含主持、负责、分管、协助、联系及企业兼任等职责，只截取其前的现任职务", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "detail_chain",
    "locator": {"css": {"leader_region_selector": ".detaillist .columnlist li a[href]", "name_selector": ".detaillist .columnlist li a", "duty_selector": ".details .introduce current-duty phrase", "detail_link_selector": ".detaillist .columnlist li a[href]", "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [".detaillist .columnlist", ".details .introduce"], "exclude_selectors": []}}, "api": {"enabled": False, "reason": "静态目录及人物详情页可稳定取得姓名、职务和详情链接"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
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
