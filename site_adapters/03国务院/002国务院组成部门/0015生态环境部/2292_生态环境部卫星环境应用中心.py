from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2292",
    "domain": "www.secmep.cn",
    "page_type": "人物目录详情页",
    "structure_group": "secmep_leader_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_secmep_leader_details_v1",
    "leader_region_selector": ".TRS_Editor",
    "name_selector": "a[href]中“姓名同志简历”",
    "duty_selector": "详情页TRS_Editor首个人物p中粗体姓名后的文本",
    "detail_link_selector": "a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".TRS_Editor"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail",
        "detail_collector_type": "static_http",
        "detail_link_selector": "a[href]",
        "detail_name_selector": ".TRS_Editor p b",
        "detail_duty_selector": ".TRS_Editor p中粗体姓名后的文本",
        "detail_content_selector": ".TRS_Editor",
        "max_detail_links": 20,
        "candidate_links": [],
    },
    "risk_flag": "目录页只提供姓名和简历链接，职务必须逐页在线核验；详情页后续文本含简历和站点链接",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".TRS_Editor",
            "name_selector": "a[href]中“姓名同志简历”",
            "duty_selector": "详情页TRS_Editor首个人物p中粗体姓名后的文本",
            "detail_link_selector": "a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".TRS_Editor"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "目录页和人物详情页均由静态HTML提供可复现字段"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online_details",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白及中文标点周边空格。"""
    text = re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()
    text = re.sub(r"\s+([，、；。])", r"\1", text)
    return re.sub(r"([，、；。])\s+", r"\1", text)


def fetch_detail_duty(session: requests.Session, detail_url: str, expected_name: str) -> str:
    """在线详情页中核对姓名，并提取同一人物首段的原始职务。"""
    clients = (session, requests.Session())
    for client in clients:
        client.headers.update({"User-Agent": "Mozilla/5.0", "Referer": detail_url})
        response = client.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        soup = BeautifulSoup(response.text, "html.parser")
        for name_node in soup.select(".TRS_Editor b, .ma b, b"):
            name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True)))
            if name != expected_name:
                continue
            container = name_node.parent
            full_text = clean_text(container.get_text(" ", strip=True) if container else "")
            duty = clean_text(full_text[len(name):]) if full_text.startswith(name) else ""
            if duty:
                return duty
        for container in soup.select(".TRS_Editor font, .ma font"):
            full_text = clean_text(container.get_text(" ", strip=True))
            if not full_text.startswith(expected_name):
                continue
            duty = clean_text(full_text[len(expected_name):])
            if duty:
                return duty
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按目录链接原始顺序逐页抽取姓名和当前职务。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；directory=a[href]姓名同志简历；detail=.TRS_Editor p b姓名+后续职务"

    for link in soup.select("a[href]"):
        label = clean_text(link.get_text(" ", strip=True))
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})同志简历", label)
        if not match:
            continue
        name = match.group(1)
        if name in seen:
            continue
        href = str(link.get("href", "")).strip()
        if not href or href.lower().startswith(("#", "javascript:", "mailto:")):
            continue
        detail_url = urljoin(final_url, href)
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            continue
        seen.add(name)
        candidates.append((name, detail_url))

    rows: list[dict[str, str]] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    try:
        bootstrap = session.get(final_url, timeout=30)
        bootstrap.raise_for_status()
    except requests.RequestException:
        return []
    for name, detail_url in candidates:
        try:
            evidence = fetch_detail_duty(session, detail_url, name)
        except requests.RequestException:
            return []
        if not evidence:
            return []
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
            }
        )
    return rows


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
