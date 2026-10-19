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
    "rule_id": "3208",
    "page_type": "人物目录详情页",
    "structure_group": "guangxi_emergency_leader_directory_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "online",
    "parser": "V011_directory_link_v1",
    "leader_region_selector": "#morelist",
    "detail_link_selector": "ul.more-list li a[href]",
    "detail_content_selector": ".article-con .trs_editor_view",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "max_detail_links": 50,
    },
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """在线解析广西壮族自治区应急管理厅领导目录及详情。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    region_selector = str(page_rule["leader_region_selector"])
    link_selector = str(page_rule["detail_link_selector"])
    detail_content_selector = str(page_rule["detail_content_selector"])
    region = soup.select_one(region_selector)
    if not region:
        raise RuntimeError(f"领导目录未命中：{region_selector}")

    rows: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for link in region.select(link_selector):
        name = re.sub(r"[\s\u115f\u1160\u3164\uffa0]+", "", link.get_text(" ", strip=True))
        href = str(link.get("href", "")).strip()
        detail_url = urljoin(final_url or str(page_rule.get("url", "")), href)
        detail_path = urlparse(detail_url).path
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name):
            continue
        if not re.search(r"/ldxx/t\d+\.shtml$", detail_path) or name in seen:
            continue

        seen.add(name)
        try:
            detail_result = fetch_html_with_strategy(
                detail_url,
                strategy=str(page_rule.get("fetch_mode", "online")),
            )
            detail_soup = BeautifulSoup(detail_result.html, "html.parser")
            detail_content = detail_soup.select_one(detail_content_selector)
            if detail_content is None:
                raise RuntimeError(f"详情正文未命中：{detail_content_selector}")
            detail_text = re.sub(r"\s+", "", detail_content.get_text(" ", strip=True))
            match = re.search(r"(现任[^。]*。)", detail_text)
            if match is None:
                raise RuntimeError("详情正文未找到现任职务句")
        except Exception as error:
            errors.append(f"{name}（{detail_url}）：{error}")
            continue

        evidence = re.sub(r"[（(]兼[）)]", "", match.group(1))
        evidence = evidence.removeprefix("现任").removesuffix("。").strip("，、； ")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": page_rule["parser"],
                "selector_summary": (
                    f"{region_selector} {link_selector} + "
                    f"{detail_content_selector} 内现任句"
                ),
            }
        )

    if errors:
        raise RuntimeError("详情采集或解析失败：" + "；".join(errors))
    if not rows:
        raise RuntimeError("领导目录未解析出有效人物详情链接")
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
