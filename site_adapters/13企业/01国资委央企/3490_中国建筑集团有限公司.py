from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def clean_text(value: str) -> str:
    """压缩详情正文中的排版空白。"""
    text = " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"\s+([，。；：、（）])", r"\1", text)
    return re.sub(r"([，。；：、（）])\s+", r"\1", text)


def parse_detail(detail_html: str, expected_name: str) -> str:
    """校验详情标题，并取得领导简介正文首句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title_node = soup.select_one("h2.gsywtpc")
    title = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
    if title != expected_name:
        return ""
    content = soup.select_one("#gsxwxq")
    if content is None:
        return ""
    for paragraph in content.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        match = re.match(r"[^。]+。", text)
        return clean_text(match.group(0)) if match else text
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """只解析当前可见的第一组领导成员，并在线读取人物详情。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    visible_group = next(
        (
            container
            for container in soup.select("div.yxj-con")
            if "display:none" not in str(container.get("style") or "").replace(" ", "").lower()
        ),
        None,
    )
    if visible_group is None:
        return []

    rows: list[dict[str, str]] = []
    for item in visible_group.select("ul.yxj-gltd > li"):
        name_node = item.select_one("h4")
        link = item.select_one("a[href]")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or link is None:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        evidence = ""
        try:
            detail_result = fetch_html_with_strategy(detail_url, "raw_http")
            evidence = parse_detail(detail_result.html, name)
        except Exception:
            evidence = ""
        evidence = evidence.rstrip("。")
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high" if evidence else "medium",
                "parser": "page_inline_cscec_visible_leaders_detail_v1",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3490",
    "page_type": "人物目录详情页",
    "structure_group": "cscec_visible_group_directory_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_cscec_visible_leaders_detail_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "同页另有 display:none 的董事会和高管标签组，只输出当前可见领导成员组；职务取详情正文首句",
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
