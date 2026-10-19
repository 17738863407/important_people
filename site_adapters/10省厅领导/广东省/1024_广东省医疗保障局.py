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
    "rule_id": "1024",
    "page_type": "多人物详情合并页",
    "structure_group": "gd_hsa_leader_index_current_sentence_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".detailm",
    "name_selector": ".detailm p",
    "duty_selector": ".detailm p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导文章编号会更新；段落含简介，仅使用当前人物段内完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = (value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐人物段提取段首姓名及完整“现任……”句。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".detailm") is None:
        article_link = next(
            (
                link
                for link in soup.select("a[href]")
                if _clean_text(link.get_text(" ", strip=True)) == "领导之窗"
                and str(link.get("href") or "").endswith(".html")
            ),
            None,
        )
        if article_link is None:
            raise RuntimeError("领导之窗栏目未找到最新领导文章")
        article_url = urljoin(final_url or page_rule["url"], str(article_link.get("href") or ""))
        article = fetch_html_with_strategy(article_url, "raw_http")
        soup = BeautifulSoup(article.html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for paragraph in soup.select(".detailm p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", re.split(r"[，,]", text, maxsplit=1)[0])
        current_match = re.search(r"现任[^。]*。", text)
        if (
            not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name)
            or current_match is None
            or name in seen
        ):
            continue
        duty = current_match.group(0).removeprefix("现任").removesuffix("。").strip()
        if not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
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
