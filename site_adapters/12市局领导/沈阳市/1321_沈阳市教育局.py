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


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(value: str) -> str:
    """移除姓名节点中的排版空格。"""
    return re.sub(r"\s+", "", str(value or "").replace("\u3000", " ").replace("\xa0", " "))


def parse_page(
    html: str,
    final_url: str,
    _page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """按领导卡片顺序抓取详情，并读取姓名段落后的职务段落。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".main-wrap1 .qw-list")
    if not cards:
        raise ValueError("未找到领导卡片 .main-wrap1 .qw-list")
    if not final_url:
        raise ValueError("在线采集结果缺少最终入口网址")

    links: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    for card in cards:
        link = card.select_one(".yangs b a[href*='bmld']")
        if link is None:
            continue
        name = clean_name(link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        links.append((name, urljoin(final_url, href)))

    if not links:
        raise ValueError("领导卡片未发现有效人物详情链接")

    rows: list[dict[str, str]] = []
    selector_summary = (
        "strategy=custom_parse_page；leader=.main-wrap1 .qw-list；"
        "name=.yangs b a[href*=bmld]；duty=#WspDetailContent .view直接子p中姓名后的下一非空段落；"
        "detail=.yangs b a[href*=bmld]"
    )
    for name, detail_url in links:
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="raw_http")
        except Exception as error:
            raise RuntimeError(f"{name}详情页采集失败：{error}") from error

        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        profile = detail_soup.select_one("#WspDetailContent .view")
        if profile is None:
            raise ValueError(f"{name}详情页未找到 #WspDetailContent .view")
        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in profile.find_all("p", recursive=False)
            if clean_text(node.get_text(" ", strip=True))
        ]
        try:
            name_index = next(index for index, text in enumerate(paragraphs) if clean_name(text) == name)
        except StopIteration as error:
            raise ValueError(f"{name}详情正文未找到独立姓名段落") from error
        if name_index + 1 >= len(paragraphs):
            raise ValueError(f"{name}详情姓名段落后缺少职务段落")
        evidence = paragraphs[name_index + 1].removesuffix("。")
        if evidence.startswith(("负责", "主持", "分管", "办公时间", "办公地址")):
            raise ValueError(f"{name}详情姓名后的段落不是职务字段")

        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url or detail_url,
                "confidence": "high",
                "parser": "page_inline_shenyang_education_detail_v1",
                "selector_summary": selector_summary,
            }
        )

    return rows


PAGE_RULE = {
    "rule_id": "1321",
    "page_type": "人物目录详情页",
    "structure_group": "shenyang_education_leader_detail",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_to_detail",
    "collector": "static_http",
    "parser": "page_inline_shenyang_education_detail_v1",
    "leader_region_selector": ".main-wrap1 .qw-list",
    "name_selector": ".yangs b a[href*='bmld']",
    "duty_selector": "#WspDetailContent .view > p[姓名段落后的下一非空段落]",
    "detail_link_selector": ".yangs b a[href*='bmld']",
    "detail_strategy": {"required": False, "mode": "inline_detail_fetch"},
    "risk_flag": "入口卡片只展示工作分工，不能作为职务；当前职务从独立人物详情的强结构职务段落取得",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".main-wrap1 .qw-list",
            "name_selector": ".yangs b a[href*='bmld']",
            "duty_selector": "#WspDetailContent .view > p[姓名段落后的下一非空段落]",
            "detail_link_selector": ".yangs b a[href*='bmld']",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态卡片和人物详情稳定提供姓名、详情链接及独立职务段落",
        },
        "migration": {
            "source": "failed_script_v3_task7",
            "verified_status": "online_verified_20260808",
            "behavior_changed": True,
        },
    },
}


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
