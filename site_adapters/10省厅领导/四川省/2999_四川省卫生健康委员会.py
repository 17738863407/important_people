from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2999",
    "page_type": "人物列表完整页",
    "structure_group": "sichuan_health_list_to_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "custom_sichuan_health_list_to_detail_v1",
    "leader_region_selector": ".zfxxgk_zd2 ul.aaa",
    "name_selector": "li a[href]",
    "duty_selector": "div.text-primary.fs-4.fw-bold + div",
    "detail_link_selector": "li a[href$='/ldxq.shtml']",
    "content_scope": {
        "start_anchor": "领导介绍",
        "end_anchor": "职能职责",
        "include_selectors": [".zfxxgk_zd2 ul.aaa"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_online_detail",
        "detail_collector_type": "requests",
        "detail_link_selector": "li a[href$='/ldxq.shtml']",
        "detail_name_selector": "div.text-primary.fs-4.fw-bold",
        "detail_duty_selector": "div.text-primary.fs-4.fw-bold + div",
        "detail_content_selector": ".p-4.rounded-3",
        "max_detail_links": 50,
    },
    "risk_flag": "入口仅列姓名；职务必须逐一在线读取详情页，禁止使用旧快照",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".zfxxgk_zd2 ul.aaa",
            "name_selector": "li a[href]",
            "duty_selector": "div.text-primary.fs-4.fw-bold + div",
            "detail_link_selector": "li a[href$='/ldxq.shtml']",
            "content_scope": {
                "start_anchor": "领导介绍",
                "end_anchor": "职能职责",
                "include_selectors": [".zfxxgk_zd2 ul.aaa"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "入口与详情页均为稳定静态HTML；详情页标题块直接提供当前职务",
        },
    },
}


def _clean_text(value: str) -> str:
    """清理HTML排版空白，不改变职务文字。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def _parse_detail(session: requests.Session, detail_url: str, expected_name: str) -> str:
    """在线读取单个人物详情页标题块中的职务。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    name_node = soup.select_one("div.text-primary.fs-4.fw-bold")
    if not name_node:
        raise RuntimeError(f"详情页缺少姓名标题：{detail_url}")

    actual_name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True))
    if actual_name != expected_name:
        raise RuntimeError(f"详情页姓名不匹配：期望{expected_name}，实际{actual_name}")

    siblings = name_node.parent.find_all("div", recursive=False)
    if len(siblings) < 2:
        raise RuntimeError(f"详情页缺少职务标题：{detail_url}")
    duty = _clean_text(siblings[1].get_text(" ", strip=True)).replace("（兼）", "").replace("(兼)", "")
    if not duty:
        raise RuntimeError(f"详情页职务为空：{detail_url}")
    return duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口姓名顺序逐一在线读取详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", final_url))
    source_host = urlparse(source_url).netloc.lower()
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": source_url})
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".zfxxgk_zd2 ul.aaa li a[href]"):
        name = re.sub(r"\s+", "", str(link.get("title") or link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen:
            continue

        candidate = urljoin(final_url or source_url, str(link.get("href") or "").strip())
        parsed = urlparse(candidate)
        real_person_page = bool(re.fullmatch(r"/scwsjkw/[^/]+/ldxq\.shtml", parsed.path))
        if parsed.netloc.lower() != source_host or not real_person_page:
            continue

        duty = _parse_detail(session, candidate, name)
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": candidate,
                "evidence": duty,
                "parser": "custom_sichuan_health_list_to_detail_v1",
                "selector_summary": "入口ul.aaa姓名原序；详情页姓名标题的相邻职务div",
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
