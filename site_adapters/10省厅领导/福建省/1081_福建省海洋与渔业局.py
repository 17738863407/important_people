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
    "rule_id": "1081",
    "domain": "hyyyj.fj.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "fujian_ocean_leader_sidebar_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_fujian_ocean_leader_sidebar_v1",
    "leader_region_selector": ".ld_list li a[href]",
    "name_selector": "h4",
    "duty_selector": "span",
    "detail_link_selector": "self[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_sidebar_links",
    },
    "risk_flag": "当前人物页侧栏列出全部省局领导；首项链接等于机构入口页，不得作为独立人物详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名节点中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def comparable_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按侧栏DOM顺序抽取姓名、原始职务和真实独立人物链接。"""
    discovered_current_page = not html
    if not html:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": str(page_rule["url"])})
        entry_parts = urlsplit(str(page_rule["url"]))
        home_url = urlunsplit((entry_parts.scheme, entry_parts.netloc, "/", "", ""))
        home_response = session.get(home_url, timeout=30)
        home_response.raise_for_status()
        home_response.encoding = home_response.apparent_encoding or "utf-8"
        home_soup = BeautifulSoup(home_response.text, "html.parser")
        leader_link = next(
            (
                link
                for link in home_soup.select("a[href]")
                if clean_text(link.get_text(" ", strip=True)) == "省局领导"
            ),
            None,
        )
        if leader_link is None:
            raise RuntimeError("官网首页未发现“省局领导”入口")
        list_url = urljoin(home_response.url, str(leader_link.get("href") or ""))
        list_response = session.get(list_url, timeout=30)
        list_response.raise_for_status()
        list_soup = BeautifulSoup(list_response.text, "html.parser")
        refresh = list_soup.select_one('meta[http-equiv="refresh"][content]')
        refresh_match = re.search(
            r"url\s*=\s*([^;]+)",
            str(refresh.get("content") if refresh else ""),
            flags=re.IGNORECASE,
        )
        if refresh_match is None:
            raise RuntimeError("省局领导栏目未发现当前人物页跳转")
        current_url = urljoin(list_response.url, refresh_match.group(1).strip(" \"'"))
        current_response = session.get(current_url, timeout=30)
        current_response.raise_for_status()
        current_response.encoding = current_response.apparent_encoding or "utf-8"
        html = current_response.text
        final_url = current_response.url

    soup = BeautifulSoup(html, "html.parser")
    entry_url = comparable_url(final_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        name_node = link.select_one(str(page_rule["name_selector"]))
        duty_node = link.select_one(str(page_rule["duty_selector"]))
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        candidate = urljoin(final_url, str(link.get("href") or ""))
        detail_url = (
            ""
            if comparable_url(candidate) == entry_url and not discovered_current_page
            else candidate
        )
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
