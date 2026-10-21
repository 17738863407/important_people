from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """压缩正文的排版空白。"""
    value = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    value = " ".join(value.split())
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    value = re.sub(r"\s+([，。；：、（）])", r"\1", value)
    return re.sub(r"([，。；：、（）])\s+", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从“姓名（职务）：分工”段落中仅提取姓名与括号内原始职务。"""
    if not html:
        html, final_url = fetch_current_article(str(page_rule["url"]))
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, str]] = []
    pattern = re.compile(r"^(.{2,8}?)\s*（([^）]+)）\s*[：:]")

    for paragraph in soup.select(".view.TRS_UEDITOR p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.match(text)
        if not match:
            continue
        name = re.sub(r"\s+", "", match.group(1))
        duty = clean_text(match.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or not duty:
            continue
        records.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_yinchuan_research_office_roles_v1",
            }
        )
    return records


def derive_category_url(source_url: str) -> str:
    """从已失效的规则文章路径推导同站领导信息栏目。"""
    parts = urlsplit(source_url)
    category_path = re.sub(r"/\d{6}/t\d{8}_\d+\.html$", "/", parts.path)
    if category_path == parts.path:
        raise RuntimeError("规则入口不符合可验证的领导栏目文章路径")
    return urlunsplit((parts.scheme, parts.netloc, category_path, "", ""))


def fetch_current_article(source_url: str) -> tuple[str, str]:
    """在线发现领导栏目中的现行领导信息稿并取得正文。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    category_result = fetch_html_with_strategy(derive_category_url(source_url), strategy="requests")
    category_soup = BeautifulSoup(category_result.html, "html.parser")
    current_link = next(
        (
            link
            for link in category_soup.select(".zfxxgk_zdgkc > ul > li > a[href]")
            if "领导信息" in clean_text(link.get_text(" ", strip=True))
        ),
        None,
    )
    if current_link is None:
        raise RuntimeError("领导栏目未发现现行领导信息稿")

    article_url = urljoin(category_result.final_url, str(current_link.get("href", "")))
    article_result = fetch_html_with_strategy(article_url, strategy="requests")
    return article_result.html, article_result.final_url


PAGE_RULE = {
    "rule_id": "3168",
    "page_type": "人物列表完整页",
    "structure_group": "yinchuan_research_name_role_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_research_office_roles_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "段落冒号后为主持、协助及分工说明，不并入主职务依据",
    "confidence": "high",
}


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
