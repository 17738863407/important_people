from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2480",
    "page_type": "人物目录详情页",
    "structure_group": "lanzhou_water_desktop_name_links_to_current_sentence_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_water_desktop_name_links_to_current_sentence_v1",
    "leader_region_selector": ".nr_left",
    "name_selector": ".nr_left dd a[href*='/col/col']",
    "duty_selector": "人物详情页.ldxx内完整现任句",
    "detail_link_selector": ".nr_left dd a[href*='/col/col']",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_to_detail",
        "detail_link_selector": ".nr_left dd a[href*='/col/col']",
        "detail_content_selector": ".ldxx",
        "max_detail_links": 10,
    },
    "risk_flag": "desktop_and_mobile_name_links_are_duplicated_and_historical_fixed_links_are_forbidden",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "desktop_region_selector": ".nr_left",
            "name_link_selector": "dd a[href*='/col/col']",
            "detail_content_selector": ".ldxx",
        },
        "api": {
            "enabled": False,
            "reason": "当前在线入口桌面区域动态提供5个姓名链接，各详情页.ldxx包含可回指完整现任句",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", cleaned)


def fetch_detail_html(session: requests.Session, detail_url: str) -> str:
    """在线读取当前人物详情页。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.text


def extract_detail_evidence(detail_html: str, expected_name: str) -> str:
    """校验详情人物归属并提取完整现任句。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    container = soup.select_one(".ldxx")
    if container is None:
        return ""
    text = normalize_space(container.get_text(" ", strip=True))
    if expected_name not in text:
        return ""
    match = re.search(r"现任[^。]{2,200}。", text)
    if not match:
        return ""
    evidence = normalize_space(match.group(0)).removeprefix("现任").removesuffix("。").rstrip()
    return re.sub(r"[（(]挂职[）)]", "", evidence).strip(" ，,；;")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按桌面姓名目录顺序，逐个在线读取详情页现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".nr_left")
    if region is None:
        return []

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in region.select("dd a[href*='/col/col']"):
        name = re.sub(r"\s+", "", normalize_space(link.get_text(" ", strip=True)))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        try:
            evidence = extract_detail_evidence(fetch_detail_html(session, detail_url), name)
        except requests.RequestException:
            continue
        if not evidence:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".nr_left桌面姓名目录顺序和动态链接；详情页.ldxx验证姓名后提取完整现任句",
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
