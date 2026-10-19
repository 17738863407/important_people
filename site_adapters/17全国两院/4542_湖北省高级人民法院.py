from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4542", "page_type": "省高级法院人物列表转详情页",
    "structure_group": "hubei_high_court_list_detail_v1", "reuse_scope": "single_page",
    "load_mode": "Playwright渲染", "extract_mode": "list_to_detail", "parser": "page_hubei_high_court_list_detail_v1",
    "leader_region_selector": ".main .list_br a[href*='/article/detail/']",
    "name_selector": "列表人物链接文本", "duty_selector": "详情页div.text中的现任句",
    "detail_link_selector": "a[href*='/article/detail/']", "detail_strategy": {"required": True, "mode": "person_detail"},
    "locator_strategy": "custom_parse_page", "inline_parser_handles_fetch": True, "inline_fetch_collector": "playwright",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "HTTP直连返回449，使用项目Playwright Chromium渲染入口并逐一读取动态发现的人物详情；按入口列表原序输出，完整保留现任句中的委员、专职委员等职务。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    entry_url = str(page_rule.get("url") or "").strip()
    if not entry_url:
        raise RuntimeError("规则主表领导链接为空，无法在线核验领导页面")
    rows: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            response = page.goto(entry_url, wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 400:
                status = response.status if response is not None else "无响应"
                raise RuntimeError(f"法院领导入口加载失败：HTTP {status}")
            page.wait_for_selector(".main .list_br a[href*='/article/detail/']", timeout=15_000)
            soup = BeautifulSoup(page.content(), "html.parser")
            links: list[tuple[str, str]] = []
            for link in soup.select(".main .list_br a[href*='/article/detail/']"):
                name = compact(link.get_text(" ", strip=True))
                detail_url = urljoin(entry_url, str(link.get("href") or ""))
                if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) and detail_url:
                    links.append((name, detail_url))
            if not links:
                raise RuntimeError("法院领导入口未发现人物详情链接")
            for name, detail_url in links:
                detail_response = page.goto(detail_url, wait_until="domcontentloaded", timeout=30_000)
                if detail_response is None or detail_response.status >= 400:
                    status = detail_response.status if detail_response is not None else "无响应"
                    raise RuntimeError(f"人物详情加载失败：HTTP {status}，{detail_url}")
                page.wait_for_selector("div.text", timeout=15_000)
                detail_soup = BeautifulSoup(page.content(), "html.parser")
                text_node = detail_soup.select_one("div.text")
                if text_node is None:
                    raise RuntimeError(f"人物详情缺少div.text正文：{detail_url}")
                detail_text = compact(text_node.get_text(" ", strip=True))
                if name not in detail_text:
                    raise RuntimeError(f"人物详情正文无法回指列表姓名：{detail_url}")
                duty_match = re.search(r"现任(.+?)(?:。|$)", detail_text)
                if duty_match is None:
                    raise RuntimeError(f"人物详情缺少现任职务句：{detail_url}")
                evidence = duty_match.group(1).strip("，,；;。 ")
                if not evidence or not re.search(r"党组|院长|政治部主任|纪检监察组组长|审判委员会委员|专职委员", evidence):
                    raise RuntimeError(f"人物详情现任句缺少可验证院级职务：{detail_url}")
                rows.append({
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": detail_url,
                    "confidence": "high",
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": ".main .list_br人物链接按DOM原序；详情div.text现任句；委员及专职委员职务完整保留",
                })
        finally:
            browser.close()
    if not rows:
        raise RuntimeError("实时领导列表及详情页未提取到合规领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
