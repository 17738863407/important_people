from __future__ import annotations

import json
import os
import re
import subprocess
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
    "rule_id": "2776",
    "domain": "tyj.hunan.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "hunan_sports_list_to_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "playwright",
    "extract_mode": "list_to_detail",
    "collector": "playwright",
    "parser": "page_inline_hunan_sports_list_to_detail_v2",
    "detail_strategy": {"required": True, "mode": "list_to_detail"},
    "risk_flag": "HTTPS requests间歇性BAD_ECPOINT；详情职务必须在线读取，禁止快照",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩页面排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def extract_detail_duty(detail_html: str) -> str:
    """从详情页独立职务行提取原文，不读取职责或简介。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    for item in soup.select("li.jdld_leader_zw"):
        label = item.find("span", recursive=False)
        if label is None or re.sub(r"\s+", "", label.get_text(" ", strip=True)).rstrip("：:") != "职务":
            continue
        text = clean_text(item.get_text(" ", strip=True))
        match = re.fullmatch(r"职\s*务\s*[：:]\s*(.+)", text)
        if match:
            return clean_text(match.group(1)).strip("，,；;。 ")
    return ""


def fetch_detail_pages(candidates: list[tuple[str, str]]) -> list[dict[str, str]]:
    """在general解释器隔离子进程中以Async Playwright抓取全部详情页。"""
    worker_code = r'''
import asyncio
import json
import sys

from playwright.async_api import async_playwright


async def main() -> None:
    candidates = json.loads(sys.stdin.read())
    results = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(ignore_https_errors=True)
        try:
            for candidate in candidates:
                result = {"name": candidate["name"], "url": candidate["url"], "html": ""}
                try:
                    response = await page.goto(
                        candidate["url"],
                        wait_until="domcontentloaded",
                        timeout=45_000,
                    )
                    if response is not None and response.ok:
                        result["html"] = await page.content()
                except Exception:
                    pass
                results.append(result)
        finally:
            await browser.close()
    print(json.dumps(results, ensure_ascii=False))


asyncio.run(main())
'''
    payload = [{"name": name, "url": detail_url} for name, detail_url in candidates]
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", worker_code],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=360,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(clean_text(completed.stderr) or "详情页Playwright隔离子进程失败")
    result = json.loads(completed.stdout)
    if not isinstance(result, list):
        raise RuntimeError("详情页Playwright隔离子进程返回格式错误")
    return result


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承列表顺序，并在同一无头浏览器会话中读取详情职务。"""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_links: set[str] = set()
    for link in soup.select("div.list1.pagelist li a[href]"):
        name = re.sub(r"\s+", "", str(link.get("title", "")) or link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, clean_text(str(link.get("href", ""))))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or detail_url in seen_links:
            continue
        seen_links.add(detail_url)
        candidates.append((name, detail_url))

    records: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in fetch_detail_pages(candidates):
        name = clean_text(str(item.get("name", ""))).replace(" ", "")
        detail_url = clean_text(str(item.get("url", "")))
        detail_html = str(item.get("html", ""))
        if not detail_html or name in seen_names:
            continue
        detail_text = re.sub(
            r"\s+",
            "",
            BeautifulSoup(detail_html, "html.parser").get_text(" ", strip=True),
        )
        duty = extract_detail_duty(detail_html)
        if name not in detail_text or not duty:
            continue
        seen_names.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=div.list1.pagelist li a[href]；"
                    "detail=li.jdld_leader_zw direct-label=职务"
                ),
            }
        )

    return records


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
