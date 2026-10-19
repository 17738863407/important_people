from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清理纯排版空白，不改变网页职务语义。"""
    return " ".join(str(value or "").replace("\u3000", " ").split())


def parse_profile(html: str, url: str, expected_name: str) -> dict[str, str] | None:
    """从人物详情页顶部强结构标题提取姓名和现职。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".m-ldshow .text")
    text = clean_text(node.get_text(" ", strip=True) if node else "")
    title_match = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,8})", text)
    duty = ""
    if title_match and title_match.group(2) == expected_name:
        duty = title_match.group(1)
    if not duty:
        profile = soup.select_one(".m-ldjj-c") or soup.select_one("#content")
        profile_text = clean_text(profile.get_text(" ", strip=True) if profile else "")
        current_match = re.search(r"现任([^。]+)", profile_text)
        duty = clean_text(current_match.group(1)) if current_match else ""
    if not duty or not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", expected_name):
        return None
    return {
        "name": expected_name,
        "duty": "",
        "evidence": duty,
        "detail_url": url,
        "confidence": "high",
        "parser": "page_inline_jingmen_government_details_v1",
    }


def fetch_profile(item: tuple[str, str]) -> dict[str, str] | None:
    """读取一个动态发现的人物详情页。"""
    import requests

    name, url = item
    session = requests.Session()
    session.trust_env = False
    response = session.get(url, timeout=35, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return parse_profile(response.text, response.url, name)


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按入口页人物卡片顺序并发读取详情，并恢复原始顺序。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    source = final_url or str(page_rule.get("url", ""))
    region = soup.select_one(".m-szfld")
    items = [
        (
            clean_text(anchor.get_text(" ", strip=True)).replace(" ", ""),
            urljoin(source, str(anchor.get("href") or "")),
        )
        for anchor in (region.select(".m-ld a[href]") if region else [])
    ]
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(fetch_profile, items))
    return [row for row in rows if row]


PAGE_RULE = {
    "rule_id": "3842",
    "page_type": "目录转领导详情页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "list_to_detail",
    "parser": "page_inline_jingmen_government_details_v1",
    "leader_region_selector": ".m-szfld",
    "name_selector": ".m-ld .text",
    "duty_selector": ".m-ldshow .text",
    "detail_link_selector": ".m-ld a[href]",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "同站多详情页联机提取",
    "confidence": "high",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        update_fetch_memory=False,
    )
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
