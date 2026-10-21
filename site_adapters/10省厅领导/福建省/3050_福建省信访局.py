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
    "rule_id": "3050",
    "domain": "xfj.fujian.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "fujian_petition_leader_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_fujian_petition_leader_detail_v1",
    "leader_region_selector": ".ldxx_left ul.jg_ul a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "detail_duty_selector": ".ld_img p",
    },
    "risk_flag": "规则入口为已下线的旧人物页；须由其父栏目实时读取meta跳转，并优先使用人物卡片中的明确职务节点，避免混入简历兼任说明",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def comparable_url(value: str) -> str:
    parts = urlsplit(value)
    path = parts.path.rstrip("/") + "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def extract_duty(detail_html: str, selector: str) -> str:
    soup = BeautifulSoup(detail_html, "html.parser")
    node = soup.select_one(selector)
    return clean_text(node.get_text(" ", strip=True) if node else "")


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def fetch_current_entry(session: requests.Session, old_entry_url: str) -> tuple[str, str]:
    """从旧人物页退回稳定父栏目，并跟随栏目当前声明的meta跳转。"""
    parent_url = urljoin(old_entry_url.rstrip("/") + "/", "../")
    response = session.get(parent_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    match = re.search(
        r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\'][^"\']*url=([^"\']+)',
        response.text,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise RuntimeError("领导信息父栏目未提供当前人物页跳转")
    current_url = urljoin(response.url, match.group(1).strip())
    return fetch_detail_html(session, current_url), current_url


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导目录原序在线取得各人物页的明确职务节点。"""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    html, final_url = fetch_current_entry(session, str(page_rule["url"]))
    soup = BeautifulSoup(html, "html.parser")
    detail_selector = str(page_rule["detail_strategy"]["detail_duty_selector"])
    entry_url = comparable_url(final_url)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(str(page_rule["leader_region_selector"])):
        name = clean_name(link.get_text(" ", strip=True))
        candidate = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            continue
        try:
            detail_html = html if comparable_url(candidate) == entry_url else fetch_detail_html(session, candidate)
        except requests.RequestException:
            continue
        evidence = extract_duty(detail_html, detail_selector)
        if not evidence:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": candidate,
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
