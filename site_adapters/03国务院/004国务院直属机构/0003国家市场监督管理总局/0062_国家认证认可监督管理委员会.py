from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0062",
    "page_type": "机构概况领导信息块",
    "structure_group": "cnca_overview_leader_block",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_cnca_overview_leader_v1",
    "leader_region_selector": ".jggk_content",
    "name_selector": "a.text-tag:first-of-type",
    "duty_selector": "a.text-tag:nth-of-type(2)",
    "detail_link_selector": "a.text-tag[href]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "机构概况",
        "include_selectors": [".jggk_content"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "item_link"},
    "risk_flag": "同页另有机构概况正文，必须以标题“领导信息”锁定首个专属内容块",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩HTML节点中的全角空格与其他排版空白。"""
    return re.sub(r"[\s\u3000\xa0]+", " ", str(value or "")).strip()


def normalize_detail_url(value: object, base_url: str) -> str:
    """还原站点防护层改写的市场监管总局跨站链接。"""
    absolute_url = urljoin(base_url, str(value or ""))
    parsed = urlsplit(absolute_url)
    host = parsed.hostname or ""
    if host.endswith(".samr.gov.cn"):
        return absolute_url
    if host.endswith(".365cyd.com.cn"):
        match = re.match(r"^1\.443\.https\.(.+?)---", host)
        if match and match.group(1).endswith(".samr.gov.cn"):
            return urlunsplit(("https", match.group(1), parsed.path, parsed.query, ""))
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从标题明确的领导信息块提取姓名、职务和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_region = next(
        (
            region
            for region in soup.select(".jggk_content")
            if clean_text(region.select_one(".jggk_tit").get_text(" ", strip=True))
            == "领导信息"
        ),
        None,
    )
    if leader_region is None:
        raise RuntimeError("未找到标题为“领导信息”的机构内容块")

    links = leader_region.select("a.text-tag[href]")
    if len(links) < 2:
        raise RuntimeError("领导信息块缺少姓名或职务链接")
    name = clean_text(links[0].get_text(" ", strip=True)).replace(" ", "")
    duty = clean_text(links[1].get_text(" ", strip=True))
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        raise RuntimeError("领导信息块中的姓名或职务格式异常")

    base_url = final_url or str(page_rule.get("url", ""))
    return [
        {
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": normalize_detail_url(links[0].get("href", ""), base_url),
            "confidence": "high",
            "parser": str(page_rule.get("parser", "")),
        }
    ]


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
