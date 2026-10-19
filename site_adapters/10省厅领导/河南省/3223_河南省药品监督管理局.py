from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3223",
    "page_type": "多人物详情合并页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".organizationleftlist",
    "row_selector": ".organizationleftlist a[href]",
    "name_selector": ".organizationleftlist a[href]",
    "duty_selector": ".leaderdetailinfo中的现任句",
    "detail_link_selector": ".organizationleftlist a[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表只提供姓名，职务须按列表顺序在线访问详情页并在当前人物简介块内提取完整现任句；入口本身是首位人物详情页。",
}


def normalize_text(text: str) -> str:
    """仅压缩网页字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def same_page(left: str, right: str) -> bool:
    """忽略协议、查询与片段比较主机和页面路径。"""
    left_parts = urlsplit(left)
    right_parts = urlsplit(right)
    return (
        left_parts.netloc.lower(),
        left_parts.path.rstrip("/") or "/",
    ) == (
        right_parts.netloc.lower(),
        right_parts.path.rstrip("/") or "/",
    )


def extract_current_sentence(html: str, expected_name: str) -> tuple[str, str]:
    """在当前人物详情块内提取可回指的完整“现任……”句。"""
    soup = BeautifulSoup(html, "html.parser")
    scope = soup.select_one(".leaderdetail")
    title = scope.select_one(".leaderdetailtitle") if scope is not None else None
    title_name = normalize_name(title.select_one("em").get_text("", strip=True)) if title and title.select_one("em") else ""
    if title_name != expected_name:
        return "", ""
    info = scope.select_one(".leaderdetailinfo")
    info_text = normalize_text(info.get_text("", strip=True) if info is not None else "")
    match = re.search(r"现任[^。]*。", info_text)
    if match is None:
        return "", ""
    evidence = match.group(0)
    return evidence.removeprefix("现任").removesuffix("。"), evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按左侧领导名单顺序在线读取各人物详情中的现任职务。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".organizationleftlist a[href]"):
        name = normalize_name(link.get_text("", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue
        fetched_url = urljoin(final_url, str(link.get("href") or ""))
        try:
            response = session.get(fetched_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
        except requests.RequestException:
            continue
        duty, evidence = extract_current_sentence(response.text, name)
        if not duty or not evidence:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "" if same_page(fetched_url, final_url) else fetched_url,
                "evidence": duty,
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
