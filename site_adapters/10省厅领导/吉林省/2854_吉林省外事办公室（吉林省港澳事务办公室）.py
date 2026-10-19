from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2854",
    "domain": "wb.jl.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "jilin_foreign_affairs_list_to_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_jilin_foreign_affairs_list_to_profile_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "增强requests误跳无障碍404页；首人页与入口同址；底部友情链接iframe排除",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def canonical_url(value: str) -> str:
    """移除查询、片段和末尾斜杠，供同址判断使用。"""
    parts = urlsplit(value)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """直接在线抓取人物详情原始HTML，并对瞬时网络错误有限重试。"""
    last_error: requests.RequestException | None = None
    for _ in range(3):
        try:
            response = session.get(detail_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("详情页在线抓取未执行")


def parse_profile(detail_html: str) -> tuple[str, str, str]:
    """从当前人物简介区域提取姓名及完整“现任……”原句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    scope = soup.select_one(".leaderRight")
    if scope is None:
        return "", "", ""
    text = clean_text(scope.get_text(" ", strip=True))
    name_match = re.search(r"简\s*历\s*[：:]\s*([\u3400-\u9fff·\s]{2,8})\s*[，,]", text)
    duty_match = re.search(r"现任\s*([^。]+)\s*。", text)
    if name_match is None or duty_match is None:
        return "", "", ""
    name = re.sub(r"\s+", "", name_match.group(1))
    duty = re.sub(r"\s+", "", duty_match.group(1)).strip("，,。 ")
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty:
        return "", "", ""
    return name, duty, duty


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承领导导航顺序，在线读取每个当前人物简介页。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".leaderLeft a[href]"):
        profile_url = urljoin(final_url, str(link.get("href", "")))
        same_as_entry = canonical_url(profile_url) == canonical_url(final_url)
        try:
            detail_html = html if same_as_entry else fetch_detail_html(session, profile_url)
        except requests.RequestException:
            continue
        name, duty, evidence = parse_profile(detail_html)
        if not name or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "" if same_as_entry else profile_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.leaderLeft a[href]；"
                    "detail=.leaderRight biography-current-sentence"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
