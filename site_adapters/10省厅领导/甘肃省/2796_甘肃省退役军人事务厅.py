from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2796",
    "page_type": "人物列表完整页",
    "structure_group": "gansu_veterans_list_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_to_detail",
    "collector": "browser_dom",
    "leader_region_selector": "div.overview_right.fr",
    "leader_heading_selector": "h1.lzyj_title",
    "leader_item_selector": "div.dalingdao, div.lzyj_list ul.ldjj > li",
    "name_selector": "p",
    "detail_link_selector": "a[href*='/ldxx/']",
    "detail_content_selector": ".view.TRS_UEDITOR.trs_paper_default.trs_web",
    "detail_strategy": {
        "required": True,
        "mode": "online_current_detail",
        "fetch_mode": "chrome",
    },
    "risk_flag": "站点存在动态防护；入口与详情均以Chrome渲染DOM为最终在线证据",
    "confidence": "high",
}


def clean_text(value: str) -> str:
    """确定性压缩网页排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    """移除姓名中的排版空白，不改变姓名字符。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\u00a0]+", "", str(value or ""))


def fetch_detail_html(detail_url: str, fetch_mode: str) -> str:
    """通过项目公共采集器取得当前人物详情页的渲染HTML。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    return fetch_html_with_strategy(detail_url, strategy=fetch_mode).html


def extract_detail_duty(detail_html: str, name: str, content_selector: str) -> str:
    """从当前详情正文中提取紧随姓名之后的原始职务段落。"""
    detail_soup = BeautifulSoup(detail_html, "html.parser")
    content = detail_soup.select_one(content_selector)
    if content is None:
        return ""

    paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in content.select("p")]
    paragraphs = [text for text in paragraphs if text]
    for index, text in enumerate(paragraphs):
        if clean_name(text) != name:
            continue
        for duty in paragraphs[index + 1 :]:
            if re.fullmatch(r"[—－-]+", duty):
                continue
            if clean_name(duty).startswith(name) and "，" in duty:
                return ""
            return duty
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口页DOM顺序解析领导卡片，并在线读取对应详情页职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        raise RuntimeError("当前页面未命中领导信息区域")

    heading = region.select_one(str(page_rule["leader_heading_selector"]))
    if heading is None or clean_text(heading.get_text(" ", strip=True)) != "领导信息":
        raise RuntimeError("当前页面未确认领导信息标题边界")

    strategy = dict(page_rule["detail_strategy"])
    content_selector = str(page_rule["detail_content_selector"])
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    errors: list[str] = []

    for item in region.select(str(page_rule["leader_item_selector"])):
        link = item.select_one(str(page_rule["detail_link_selector"]))
        name_node = item.select_one(str(page_rule["name_selector"]))
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        if link is None or not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or name in seen:
            continue

        detail_url = urljoin(final_url, str(link.get("href") or "").strip())
        detail_path = urlparse(detail_url).path
        if not re.fullmatch(r"/tyjr/ldxx/\d{6}/\d+\.shtml", detail_path):
            errors.append(f"{name}详情链接不符合当前人物详情页结构：{detail_url}")
            continue

        try:
            detail_html = fetch_detail_html(detail_url, str(strategy["fetch_mode"]))
            evidence = extract_detail_duty(detail_html, name, content_selector)
        except Exception as error:
            errors.append(f"{name}详情页采集失败：{error}")
            continue
        if not evidence:
            errors.append(f"{name}详情页未取得紧随姓名的原始职务段落")
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

    if errors:
        raise RuntimeError("；".join(errors))
    if not rows:
        raise RuntimeError("当前领导信息区域未解析到有效人物")
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
