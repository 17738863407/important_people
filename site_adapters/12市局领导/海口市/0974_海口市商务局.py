from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0974",
    "page_type": "人物列表完整页",
    "structure_group": "haikou_commerce_dynamic_leader_channel",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".gkpd-ld, .gkpd-ldd",
    "name_selector": "主人物与补充人物容器链接方括号前",
    "duty_selector": "主人物与补充人物容器链接方括号内",
    "detail_link_selector": ".gkpd-ld a[href], .gkpd-ldd a[href]",
    "detail_strategy": {"required": False, "mode": "links_from_listing", "max_detail_links": 50},
    "risk_flag": "规则入口为法定公开目录，须动态发现同站领导信息栏目并验证姓名方括号职务链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", "", str(value or "")).strip()


def find_leader_page(html: str, final_url: str) -> tuple[BeautifulSoup, str]:
    index_soup = BeautifulSoup(html, "html.parser")
    host = urlparse(final_url).netloc
    candidates: list[str] = []
    for link in index_soup.select("a[href]"):
        if "领导信息" not in clean_text(link.get_text(" ", strip=True)):
            continue
        candidate = urljoin(final_url, str(link.get("href") or ""))
        if urlparse(candidate).netloc == host and candidate not in candidates:
            candidates.append(candidate)
    errors: list[str] = []
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for candidate in candidates:
            try:
                response = session.get(candidate, timeout=30, verify=False)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or response.encoding
                soup = BeautifulSoup(response.text, "html.parser")
                selector = ".gkpd-ld a[href], .gkpd-ldd a[href]"
                if any("[" in link.get_text(" ", strip=True) for link in soup.select(selector)):
                    return soup, response.url
                errors.append(f"{candidate}:未发现人物链接")
            except Exception as error:
                errors.append(f"{candidate}:{error}")
    raise ValueError("未能从规则入口动态发现有效领导信息栏目：" + "；".join(errors))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup, leader_url = find_leader_page(html, final_url)
    pattern = re.compile(r"^(?P<name>[\u3400-\u9fff·]{2,12})\[(?P<duty>[^\]]+)\]$")
    rows: list[dict[str, str]] = []
    for link in soup.select(".gkpd-ld a[href], .gkpd-ldd a[href]"):
        match = pattern.fullmatch(clean_text(link.get_text(" ", strip=True)))
        href = str(link.get("href") or "").strip()
        if not match or not href:
            continue
        duty = match.group("duty")
        rows.append({"name": match.group("name"), "duty": duty, "evidence": duty,
                     "detail_url": urljoin(leader_url, href),
                     "selector_summary": "规则入口动态发现领导栏目→.gkpd-ld姓名方括号职务链接"})
    if not rows:
        raise ValueError("动态领导栏目未解析出有效人物记录")
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
