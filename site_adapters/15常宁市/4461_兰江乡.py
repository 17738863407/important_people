from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4461", "page_type": "乡镇领导信息目录",
    "structure_group": "changning_township_leader_directory_v1",
    "load_mode": "防护页后静态HTML", "extract_mode": "custom",
    "parser": "page_inline_changning_leader_directory_v1",
    "leader_region_selector": "领导信息目录列表",
    "detail_strategy": {"required": True, "mode": "directory_item_link"},
    "risk_flag": "站点可能返回412 JavaScript防护页；仅解析入口动态发现的领导信息目录。",
    "confidence": "medium", "filter_policy": "strong_no_wordlist",
    "locator_strategy": "leader_directory_title_and_link",
}


def clean_text(value: str) -> str:
    """清除纯排版空白。"""
    return re.sub(r"[\s\u00a0\u200b\u3000]+", " ", value or "").strip()


def find_leader_directory(html: str, final_url: str) -> str:
    """从乡镇入口动态发现领导信息目录。"""
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        label = clean_text(anchor.get_text(" ", strip=True)).replace(" ", "")
        href = str(anchor.get("href") or "").strip()
        if label == "领导信息" and "/gzjg/ldxx" in href:
            return urljoin(final_url, href)
    raise RuntimeError("乡镇入口未发现可验证的领导信息目录链接")


def split_title(text: str) -> tuple[str, str]:
    """拆分标题末尾姓名并保留完整职务证据。"""
    normalized = clean_text(text)
    match = re.search(r"(?:[：:]|\s)([\u3400-\u9fff·]{2,6})\s*$", normalized)
    if match is None:
        return "", ""
    return match.group(1), normalized[: match.start()].rstrip(" ：:")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按目录 DOM 顺序提取标题证据和人物页。"""
    from crawler_core.fetcher import fetch_html_with_preferred_fallback
    result = fetch_html_with_preferred_fallback(
        find_leader_directory(html, final_url), preferred_strategy="raw_http", timeout=30
    )
    directory_path = urlparse(result.final_url).path.rstrip("/")
    prefix = directory_path.rsplit("/", 1)[0] if directory_path.endswith(".html") else directory_path
    rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for anchor in BeautifulSoup(result.html, "html.parser").find_all("a", href=True):
        detail_url = urljoin(result.final_url, str(anchor.get("href") or ""))
        detail_path = urlparse(detail_url).path.rstrip("/")
        if not detail_path.startswith(prefix + "/") or detail_path == directory_path or detail_url in seen_urls:
            continue
        name, duty = split_title(str(anchor.get("title") or anchor.get_text(" ", strip=True)))
        if name and duty:
            seen_urls.add(detail_url)
            rows.append({"name": name, "duty": duty, "detail_url": detail_url, "evidence": duty,
                         "parser": str(page_rule["parser"]),
                         "selector_summary": "领导信息目录内人物条目标题与独立详情链接"})
    if not rows:
        raise RuntimeError("领导信息目录未发现可验证的职务—姓名条目")
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
