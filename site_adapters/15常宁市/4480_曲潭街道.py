from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def discover_leader_url(html: str, final_url: str) -> str:
    """从规则主表将来注入的入口页导航动态发现领导信息栏目。"""
    soup = BeautifulSoup(html or "", "html.parser")
    urls = list(dict.fromkeys(
        urljoin(final_url, str(a.get("href") or "").strip())
        for a in soup.select("a[href]")
        if clean_text(a.get_text(" ", strip=True)) == "领导信息"
        and str(a.get("href") or "").strip()
    ))
    if len(urls) != 1:
        raise RuntimeError(f"入口页领导信息栏目链接数量异常：{len(urls)}")
    return urls[0]


def extract_leader_rows(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按领导栏目 DOM 顺序抽取人物文章。"""
    soup = BeautifulSoup(html or "", "html.parser")
    base_path = urlparse(final_url).path.rsplit("/", 1)[0] + "/"
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    for anchor in soup.select("a[href]"):
        detail_url = urljoin(final_url, str(anchor.get("href") or ""))
        path = urlparse(detail_url).path
        if detail_url in seen_urls or not path.startswith(base_path):
            continue
        if re.search(r"/\d{8}/i\d+\.html$", path) is None:
            continue
        title = clean_text(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
        parts = re.split(r"[：:]", title)
        if len(parts) < 2:
            continue
        name = clean_text(parts[-1]).replace(" ", "")
        duty = clean_text("：".join(parts[:-1])).rstrip("。；; ")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not duty:
            continue
        if name in seen_names:
            raise RuntimeError(f"领导栏目出现重复姓名：{name}")
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": detail_url,
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
            "selector_summary": "领导信息栏目人物文章锚点的职务：姓名标题",
        })
        seen_urls.add(detail_url)
        seen_names.add(name)
    if not rows:
        raise RuntimeError("领导信息栏目未提取到当前人物文章")
    return rows


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    leader_url = discover_leader_url(html, final_url)
    page = fetch_html_with_strategy(leader_url, strategy="online", timeout=45)
    return extract_leader_rows(page.html, page.final_url, page_rule)


PAGE_RULE = {
    "rule_id": "4480",
    "page_type": "街道入口转领导信息文章列表",
    "structure_group": "changning_town_leader_article_list_v1",
    "reuse_scope": "same_site_same_structure",
    "load_mode": "浏览器渲染入口并动态请求领导栏目",
    "extract_mode": "list_to_detail",
    "parser": "page_changning_town_leader_article_list_v1",
    "leader_region_selector": "导航中标题为领导信息的栏目及其文章列表",
    "name_selector": "领导文章锚点标题末尾冒号后的姓名",
    "duty_selector": "领导文章锚点标题末尾冒号前的完整职务",
    "detail_link_selector": "领导栏目内日期文章链接",
    "detail_strategy": {"required": True, "mode": "current_person_article"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "规则主表入口暂为空；脚本不保存候选入口，待权威业务源补齐后从页面导航动态发现领导栏目",
    "confidence": "pending_online_verification",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
