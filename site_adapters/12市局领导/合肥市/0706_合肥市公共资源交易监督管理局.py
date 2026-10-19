from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0706",
    "page_type": "人物目录详情页",
    "structure_group": "hefei_public_single_profile_directory",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 8000,
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "directory_detail",
    "collector": "browser_dom",
    "parser": "hefei_public_resource_single_profile_detail_v1",
    "leader_region_selector": "#xxgk_lmcon .inner-list .page-list .xxgk-tab-content table.xxgk-table-list > tbody > tr",
    "name_selector": "",
    "duty_selector": "#zoom p",
    "detail_link_selector": "td.title-td > a.title[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "栏目首项为全体工作分工，只接受详情正文中唯一单人物现任简介结构",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写语义内容。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _extract_profile(detail_html: str) -> tuple[str, str]:
    """仅接受详情正文中唯一的“姓名……现任……。”人物简介段。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    region = soup.select_one("#zoom")
    if region is None:
        return "", ""

    candidates: list[tuple[str, str]] = []
    for paragraph in region.select("p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[一-鿿·\s]{2,12})[，,]", text)
        duty_match = re.search(r"现任[^。]*。", text)
        if not name_match or not duty_match:
            continue
        name = re.sub(r"\s+", "", name_match.group("name"))
        if re.fullmatch(r"[一-鿿·]{2,8}", name):
            candidates.append((name, _clean_text(duty_match.group(0))))
    if len(candidates) != 1:
        return "", ""
    name, evidence = candidates[0]
    evidence = re.sub(r"^现任\s*", "", evidence).removesuffix("。").strip()
    return name, evidence


def _validate_detail_url(href: str, final_url: str) -> str:
    """只接受栏目当前行动态提供的同域公开详情页。"""
    detail_url = urljoin(final_url, href)
    entry = urlparse(final_url)
    detail = urlparse(detail_url)
    if detail.netloc != entry.netloc:
        return ""
    if not re.fullmatch(r"/public/6231/\d+\.html", detail.path):
        return ""
    return detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按栏目 DOM 顺序筛选并解析独立单人物简介页。"""
    from crawler_core.fetcher import fetch_by_playwright
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(page_rule["leader_region_selector"])
    if not rows:
        raise RuntimeError("机构领导栏目表格选择器未命中")

    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for row in rows:
        link = row.select_one(page_rule["detail_link_selector"])
        if link is None:
            continue
        detail_url = _validate_detail_url(str(link.get("href", "")), final_url)
        if not detail_url or detail_url in seen_urls:
            continue

        detail_result = fetch_by_playwright(detail_url, timeout=60)
        name, evidence = _extract_profile(detail_result.html)
        if not name and not evidence:
            continue
        title_text = re.sub(r"\s+", "", _clean_text(link.get_text(" ", strip=True)))
        if name not in title_text:
            raise RuntimeError(f"详情姓名未回指栏目标题：{name}，标题={title_text}")
        if name in seen_names:
            raise RuntimeError(f"栏目出现重复人物：{name}")

        final_detail_url = detail_result.final_url
        if not _validate_detail_url(final_detail_url, final_url):
            raise RuntimeError(f"详情最终地址不符合栏目路径：{final_detail_url}")
        seen_names.add(name)
        seen_urls.add(detail_url)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=final_detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("栏目详情页中未找到可验证的单人物现任简介")
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
