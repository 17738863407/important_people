from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1760",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_civil_affairs_iframe_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright_then_enhanced_requests",
    "parser": "page_nanjing_civil_affairs_iframe_profile_v2",
    "leader_region_selector": "渲染后#xxgk_215当前链接 -> frame #znjj",
    "name_selector": "#znjj人物简介段首个逗号前",
    "duty_selector": "同一人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "站点证书链异常且入口JavaScript导航实际frame，需Playwright发现地址并用增强请求SSL降级抓取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"frame_url_selector": "#xxgk_215 a[href]", "leader_region_selector": "#znjj", "row_selector": "#znjj p"},
        "api": {"enabled": False, "reason": "渲染后当前栏目链接指向领导概况页，增强HTTP请求可处理站点证书异常"},
    },
}


def normalize_layout(text: str) -> str:
    """确定性清理富文本编辑器产生的中文排版空白。"""
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    value = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", value)


def fetch_frame_html(main_html: str, final_url: str) -> str:
    """从渲染后的入口当前栏目链接发现frame，并使用公共增强请求抓取正文。"""
    soup = BeautifulSoup(main_html, "html.parser")
    current_link = soup.select_one("#xxgk_215 a[href]")
    frame_url = urljoin(final_url, str(current_link.get("href", "")).strip()) if current_link else ""
    if not frame_url or frame_url == final_url:
        raise RuntimeError("渲染后的入口页未发现有效#xxgk_215当前栏目地址")

    from crawler_core.fetcher import fetch_html_with_strategy

    fetch_result = fetch_html_with_strategy(frame_url, strategy="requests")
    return fetch_result.html


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按实际frame #znjj人物简介段顺序提取姓名和完整现任句。"""
    soup = BeautifulSoup(fetch_frame_html(html, final_url), "html.parser")
    region = soup.select_one("#znjj")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_layout(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        evidence = evidence_match.group(0)
        duty = evidence.removeprefix("现任").removesuffix("。")
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "Playwright渲染入口后动态发现frame；公共增强requests处理SSL异常；frame #znjj p按DOM顺序提取段首姓名与完整现任句",
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
