from __future__ import annotations

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def _fetch_expanded_management_html_sync(entry_url: str) -> str:
    """使用无头Playwright切换到经营管理层，并点击展开全部人物。"""
    from crawler_core.fetcher import connect_chrome_debug_browser, warm_up_browser_context
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = connect_chrome_debug_browser(playwright, timeout=60)
        if not browser.contexts:
            raise RuntimeError("项目Chrome CDP没有可用浏览器上下文")
        context = browser.contexts[0]
        warm_up_browser_context(context, entry_url, timeout=60)
        page = context.new_page()
        try:
            page.goto(entry_url, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            entry_soup = BeautifulSoup(page.content(), "html.parser")
            management_anchor = next(
                (
                    link
                    for link in entry_soup.select("a[href]")
                    if clean_text(link.get_text(" ", strip=True)) == "经营管理层"
                ),
                None,
            )
            if management_anchor is None:
                page_text = clean_text(page.locator("body").inner_text())[:200]
                raise RuntimeError(
                    f"Chrome入口页缺少经营管理层链接：url={page.url}；"
                    f"title={page.title()}；text={page_text}"
                )
            href = str(management_anchor.get("href") or "").strip()
            if not href:
                raise RuntimeError("入口页未找到“经营管理层”的可验证链接")
            management_url = urljoin(page.url, href)
            page.goto(management_url, wait_until="domcontentloaded", timeout=60_000)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

            management_soup = BeautifulSoup(page.content(), "html.parser")
            tab_node = next(
                (
                    button
                    for button in management_soup.select("button[aria-controls]")
                    if clean_text(button.get_text(" ", strip=True)) == "经营管理层"
                ),
                None,
            )
            if tab_node is None:
                raise RuntimeError("经营管理层页面未找到对应的 aria-controls 标签")
            control_id = str(tab_node.get("aria-controls") or "").strip()
            if not control_id:
                raise RuntimeError("经营管理层标签缺少 aria-controls 分组关联")
            page.locator(f"button[aria-controls='{control_id}']").first.click(force=True)
            slide = page.locator(f"#{control_id}")
            slide.wait_for(state="visible", timeout=20_000)

            hidden_items = slide.locator("li.hide-on-arrow-more")
            if hidden_items.count() > 0:
                more_button = slide.locator(".app-more-arrow .arrow").first
                more_button.wait_for(state="visible", timeout=20_000)
                more_button.scroll_into_view_if_needed()
                more_button.click()
                page.wait_for_function(
                    """
                    (slideId) => Array.from(
                      document.querySelectorAll(`#${slideId} li.hide-on-arrow-more`)
                    ).every((item) => getComputedStyle(item).display !== 'none')
                    """,
                    arg=control_id,
                    timeout=20_000,
                )
            return slide.inner_html()
        finally:
            page.close()


def fetch_expanded_management_html(entry_url: str) -> str:
    """在线程中隔离同步Playwright，避免与公共运行器的异步事件循环冲突。"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_fetch_expanded_management_html_sync, entry_url).result()


def clean_text(value: str) -> str:
    """清理页面字段中的纯排版空白和零宽字符。"""
    text = re.sub(r"[\s\u3000\u00a0\u2000-\u200d\ufeff]+", " ", str(value or "")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """只从已切换并展开的“经营管理层”分组抽取人物和第一句现职。"""
    entry_url = str(page_rule.get("url") or final_url or "").strip()
    if not entry_url:
        raise RuntimeError("未取得规则主表注入的机构入口链接")
    soup = BeautifulSoup(fetch_expanded_management_html(entry_url), "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in soup.select(".app-about-leadership-list li:has(.name):has(.intro)"):
        if "display:none" in re.sub(r"\s+", "", str(item.get("style") or "")).lower():
            raise RuntimeError("点击展开后仍存在隐藏的经营管理层人物卡片")
        name_node = item.select_one(".name")
        intro_node = item.select_one(".intro")
        raw_name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        name = re.sub(r"(先生|女士)$", "", raw_name)
        intro = clean_text(intro_node.get_text(" ", strip=True) if intro_node else "")
        duty = intro.split("。", 1)[0].rstrip("。；; ")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            raise RuntimeError(f"经营管理层姓名格式异常：{name or '<空>'}")
        if not duty:
            raise RuntimeError(f"{name} 的现职首句为空")
        if name in seen_names:
            raise RuntimeError(f"经营管理层姓名重复：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "ctg_management_group_v2",
                "selector_summary": "经营管理层tab[aria-controls]；展开全部；组内name与intro首句",
            }
        )
    if not rows:
        raise RuntimeError("经营管理层分组展开后未提取到人物卡片")
    return rows


PAGE_RULE = {
    "rule_id": "3542",
    "page_type": "职务分组名单页",
    "structure_group": "ctg_leadership_carousel",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染与交互展开",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_direct",
    "collector": "playwright_interactive",
    "parser": "ctg_management_group_v2",
    "leader_region_selector": "经营管理层tab[aria-controls]关联的轮播分组",
    "name_selector": ".name",
    "duty_selector": ".intro第一完整句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时含董事会与经营管理层；只跟随经营管理层链接和aria-controls分组，并点击展开按钮后采集全部可见卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "risk_note": "只解析经营管理层分组，不采集董事会；职务只取简介首个完整句，不混入学历、加入年份。",
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
