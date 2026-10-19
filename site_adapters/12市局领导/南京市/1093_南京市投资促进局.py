from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1093",
    "page_type": "人物列表完整页",
    "structure_group": "nanjing_investment_iframe_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "playwright",
    "extract_mode": "custom_parse_page",
    "collector": "playwright_then_iframe_http",
    "parser": "page_nanjing_investment_iframe_profile_v2",
    "leader_region_selector": "渲染后#xxgk_215当前链接 -> frame #heightbox2",
    "name_selector": "#heightbox2人物简介段首个逗号前",
    "duty_selector": "同一人物简介段内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "detail_link_selector": "", "max_detail_links": 0},
    "risk_flag": "入口iframe初始地址回跳且JavaScript导航实际frame，必须渲染后动态发现当前栏目地址",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {"frame_url_selector": "#xxgk_215 a[href]", "leader_region_selector": "#heightbox2", "row_selector": "#heightbox2 p"},
        "api": {"enabled": False, "reason": "入口渲染后当前栏目链接指向包含领导简介的frame静态正文页"},
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白。"""
    value = re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()
    return re.sub(r"\s*([、，。；：])\s*", r"\1", value)


def clean_current_evidence(text: str) -> str:
    """删除固定现任标签、句末句号及明确尾随的主持全面工作职责。"""
    evidence = re.sub(r"^现任\s*", "", normalize_space(text))
    evidence = re.sub(r"。$", "", evidence).strip()
    return re.sub(r"[，；;]\s*主持[^，；;。]*全面工作$", "", evidence).strip()


def fetch_frame_html(main_html: str, final_url: str) -> str:
    """从渲染后的入口当前栏目链接动态发现并抓取frame正文。"""
    soup = BeautifulSoup(main_html, "html.parser")
    current_link = soup.select_one("#xxgk_215 a[href]")
    frame_url = urljoin(final_url, str(current_link.get("href", "")).strip()) if current_link else ""
    if not frame_url or frame_url == final_url:
        raise RuntimeError("渲染后的入口页未发现有效#xxgk_215当前栏目地址")
    response = requests.get(
        frame_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": final_url,
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按实际frame人物简介段顺序提取姓名和完整“现任……”原句。"""
    soup = BeautifulSoup(fetch_frame_html(html, final_url), "html.parser")
    region = soup.select_one("#heightbox2")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        text = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,8})，", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if name_match is None or evidence_match is None:
            continue
        name = name_match.group("name")
        evidence = clean_current_evidence(evidence_match.group(0))
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "Playwright渲染入口后从#xxgk_215当前链接动态发现frame；#heightbox2 p按DOM顺序；段首姓名与同段完整现任句",
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
