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
    "rule_id": "2766",
    "domain": "tyj.gansu.gov.cn",
    "page_type": "人物列表链接加详情页简介",
    "structure_group": "gansu_sports_leader_detail_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "browser_render_wait_ms": 3000,
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "browser_dom",
    "parser": "page_inline_gansu_sports_leader_detail_profiles_v2",
    "leader_region_selector": ".ldzc .zfxxgkbox",
    "leader_link_selector": "a[href*='/ldlist.shtml']",
    "detail_strategy": {
        "required": False,
        "mode": "current_leader_links",
    },
    "risk_flag": "普通HTTP返回412防护页；入口多数链接只显示姓名，须按入口顺序用Chrome CDP读取当前详情页简介中的现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def extract_list_name(value: str) -> str:
    """从链接开头取得姓名；列表可能仅显示姓名，也可能追加职务和“个人简介”。"""
    text = clean_text(value)
    name_text = re.split(r"\s*(?:局党组|党组|局长|副局长|个人简介)", text, maxsplit=1)[0]
    name = re.sub(r"[\s\u3000\u00a0]+", "", name_text)
    return name if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) else ""


def fetch_current_duty(detail_url: str, name: str) -> str:
    """只在当前人物详情简介块中提取网页明确写出的完整现任职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(detail_url, strategy="chrome_cdp", timeout=30)
    soup = BeautifulSoup(result.html, "html.parser")
    region = soup.select_one(".leader_disc .disc")
    if region is None:
        return ""
    profile = clean_text(region.get_text(" ", strip=True))
    if name not in re.sub(r"[\s\u3000\u00a0]+", "", profile):
        return ""
    match = re.search(r"现任([^。；]+)", profile)
    return clean_text(match.group(1)).strip("：:，,。.；;") if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按渲染后领导之窗链接顺序解析姓名、职务和人物链接。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in region.select(str(page_rule["leader_link_selector"])):
        name = extract_list_name(link.get_text(" ", strip=True))
        if not name or name in seen:
            continue
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        evidence = fetch_current_duty(detail_url, name)
        if not evidence:
            continue
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
