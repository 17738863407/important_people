from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0766",
    "page_type": "人物列表完整页",
    "structure_group": "nanning_industry_it_list_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_list_then_detail_http",
    "parser": "page_nanning_industry_it_list_detail_v2",
    "leader_region_selector": ".news_list领导简介块",
    "name_selector": "详情正文首段同志前姓名",
    "duty_selector": "详情正文首段冒号后完整职务",
    "detail_link_selector": ".news_list .nav1Cont a[href]",
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_link_selector": ".news_list .nav1Cont a[href]", "max_detail_links": 30},
    "risk_flag": "页面还含部门介绍和内设机构，必须只遍历标题为领导简介的块，并以详情首段取得完整机构职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"leader_region_selector": ".news_list", "block_title_selector": ".navtxt", "detail_link_selector": ".nav1Cont a[href]", "detail_content_selector": ".TRS_UEDITOR, .TRS_Editor"},
        "api": {"enabled": False, "reason": "领导简介列表和人物详情正文均由静态HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def discover_detail_urls(html: str, final_url: str) -> list[str]:
    """仅从标题为领导简介的区块按DOM顺序发现详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for block in soup.select(".news_list"):
        title = block.select_one(".navtxt")
        if title is None or normalize_layout(title.get_text(" ", strip=True)) != "领导简介":
            continue
        for anchor in block.select(".nav1Cont a[href]"):
            detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
            if not detail_url or detail_url in seen:
                continue
            seen.add(detail_url)
            urls.append(detail_url)
    return urls


def parse_detail(html: str) -> tuple[str, str]:
    """从人物详情正文首个非空段提取姓名和完整原始职务节点。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_UEDITOR, .TRS_Editor")
    if region is None:
        return "", ""
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})同志：(?P<duty>.+)$", text)
        if match is None:
            return "", ""
        return match.group("name"), match.group("duty").strip()
    return "", ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持领导简介列表顺序，逐详情提取完整姓名职务首段。"""
    detail_urls = discover_detail_urls(html, final_url)
    if not detail_urls:
        return []

    from crawler_core.fetcher import fetch_html_with_strategy

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for detail_url in detail_urls:
        detail_html = fetch_html_with_strategy(detail_url, strategy="requests").html
        name, evidence = parse_detail(detail_html)
        if not name or not evidence:
            raise RuntimeError(f"人物详情页缺少可验证的姓名职务首段：{detail_url}")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "标题为领导简介的.news_list链接按DOM顺序；逐详情正文首个非空p提取姓名同志：完整职务原文",
            }
        )
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
