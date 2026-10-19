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
    "rule_id": "0820",
    "domain": "gzw.fujian.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "fujian_sasac_leader_navigation_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_fujian_sasac_leader_navigation_detail_v1",
    "leader_region_selector": "ul.ld_list.down a[href]",
    "name_selector": "self_text",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "detail_content_selector": ".ld_tu",
    },
    "risk_flag": "领导导航仅含姓名，职务在各人物页.ld_tu且与姓名同节点；须在线取详情并移除末尾同名副本",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def compact_text(value: str) -> str:
    """移除页面用于姓名排版的空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def comparable_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def extract_duty(detail_html: str, name: str, selector: str) -> str:
    """从职务姓名同节点中确定性移除末尾当前姓名。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    node = soup.select_one(selector)
    if node is None:
        return ""
    compact = compact_text(node.get_text(" ", strip=True))
    compact_name = compact_text(name)
    if not compact.endswith(compact_name):
        return ""
    return compact[: -len(compact_name)].strip("：:")


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    response = session.get(detail_url, timeout=30, verify=False)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导导航顺序在线取得各人物页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    detail_selector = str(page_rule["detail_strategy"]["detail_content_selector"])
    entry_url = comparable_url(final_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        name = compact_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            continue
        candidate = urljoin(final_url, str(link.get("href") or ""))
        try:
            detail_html = html if comparable_url(candidate) == entry_url else fetch_detail_html(session, candidate)
        except requests.RequestException:
            continue
        evidence = extract_duty(detail_html, name, detail_selector)
        if not evidence:
            continue
        detail_url = "" if comparable_url(candidate) == entry_url else candidate
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
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
