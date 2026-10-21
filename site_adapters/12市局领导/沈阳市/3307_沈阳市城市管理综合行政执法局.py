from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def build_page_rule(rule_id: str) -> dict[str, object]:
    """构造当前页面的DeepSeek图片视觉解析规则。"""
    from crawler_core.vision_llm import build_vision_page_rule
    rule = build_vision_page_rule(
        rule_id,
        ".view.TRS_UEDITOR img[oldsrc], .view.TRS_UEDITOR img[src]",
        "部门领导由多张图片承载；逐张抽取姓名及标题行中的现任职务，忽略分工正文。",
    )
    rule["inline_parser_handles_fetch"] = True
    rule["inline_fetch_collector"] = "requests"
    return rule


def derive_category_url(source_url: str) -> str:
    """从已失效的规则文章路径推导同站部门领导栏目。"""
    parts = urlsplit(source_url)
    category_path = re.sub(r"/\d{6}/t\d{8}_\d+\.html$", "/", parts.path)
    if category_path == parts.path:
        raise RuntimeError("规则入口不符合可验证的部门领导文章路径")
    return urlunsplit((parts.scheme, parts.netloc, category_path, "", ""))


def fetch_current_article(source_url: str) -> tuple[str, str]:
    """在线发现部门领导栏目中的现行领导信息稿。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    category_result = fetch_html_with_strategy(derive_category_url(source_url), strategy="requests")
    category_soup = BeautifulSoup(category_result.html, "html.parser")
    current_link = next(
        (
            link
            for link in category_soup.select("a[href]")
            if "领导" in link.get_text(" ", strip=True) and "信息" in link.get_text(" ", strip=True)
        ),
        None,
    )
    if current_link is None:
        raise RuntimeError("部门领导栏目未发现现行领导信息稿")
    article_url = urljoin(category_result.final_url, str(current_link.get("href", "")))
    article_result = fetch_html_with_strategy(article_url, strategy="requests")
    return article_result.html, article_result.final_url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[object]:
    """运行DeepSeek V4 Flash视觉抽取和证据解析。"""
    from crawler_core.vision_llm import parse_vision_llm_records
    from crawler_core.settings import get_settings
    if not html:
        html, final_url = fetch_current_article(str(page_rule["url"]))
    return parse_vision_llm_records(page_rule, html, final_url, get_settings().browser_timeout_seconds)


def main(rule_id: str) -> None:
    """运行当前图片人物脚本。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(build_page_rule(rule_id), globals(), project_dir / "outputs")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3307"
    main(rule_id_value)
