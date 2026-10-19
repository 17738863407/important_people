from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0646",
    "page_type": "人物目录详情页",
    "structure_group": "guizhou_broadcast_leader_window_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "requests",
    "parser": "inline_parse_page",
    "leader_region_selector": ".ldzc_right li",
    "name_selector": ".ldzc_right li a[title]",
    "duty_selector": ".ldzc_left .xldr_profile",
    "detail_link_selector": ".ldzc_right li a[title][href]",
    "content_scope": {
        "include_selectors": [".ldzc_right", ".ldzc_left .xldr_profile"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_raw_http_detail",
        "detail_content_selector": ".ldzc_left .xldr_profile",
    },
    "risk_flag": "入口仅展开当前人物，必须逐个详情核对姓名并提取领导职务原文，排除领导分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def normalize_text(value: str) -> str:
    """只压缩HTML文本中的排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").split())


def parse_detail(html: str, expected_name: str, detail_url: str) -> dict[str, str]:
    """解析详情页姓名和“领导职务”字段，排除后续领导分工。"""
    soup = BeautifulSoup(html, "html.parser")
    profile = soup.select_one(".ldzc_left .xldr_profile")
    if profile is None:
        raise ValueError(f"人物详情页缺少领导资料容器：{detail_url}")
    profile_text = normalize_text(profile.get_text(" ", strip=True))
    name_match = re.search(r"([\u3400-\u9fff·]{2,20})\s*同志", profile_text)
    duty_match = re.search(r"领导职务\s*[：:]\s*(.*?)\s*领导分工\s*[：:]", profile_text)
    name = re.sub(r"\s+", "", name_match.group(1)) if name_match else ""
    duty = normalize_text(duty_match.group(1)) if duty_match else ""
    if name != expected_name:
        raise ValueError(f"入口姓名与详情姓名不一致：{expected_name!r} != {name!r}，页面={detail_url}")
    if not duty:
        raise ValueError(f"人物详情页缺少领导职务原文：{detail_url}")
    return {
        "name": name,
        "duty": duty,
        "evidence": duty,
        "detail_url": detail_url,
    }


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口列表顺序逐个获取并解析当前领导详情。"""
    del page_rule
    from crawler_core.fetcher import fetch_by_raw_requests

    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select(".ldzc_right li a[title][href]")
    if not anchors:
        raise ValueError("领导之窗入口未发现人物详情链接")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for anchor in anchors:
        expected_name = re.sub(r"\s+", "", normalize_text(str(anchor.get("title") or anchor.get_text(" ", strip=True))))
        detail_url = urljoin(final_url, str(anchor.get("href") or "").strip())
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", expected_name):
            raise ValueError(f"入口人物姓名格式异常：{expected_name!r}")
        if expected_name in seen_names or detail_url in seen_urls:
            continue
        result = fetch_by_raw_requests(detail_url)
        rows.append(parse_detail(result.html, expected_name, result.final_url))
        seen_names.add(expected_name)
        seen_urls.add(detail_url)
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
