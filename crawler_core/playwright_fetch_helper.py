from __future__ import annotations

import argparse
import json
import sys
import traceback

from crawler_core.settings import get_settings
from crawler_core.fetcher import (
    configure_browser_context,
    get_browser_context_options,
    get_playwright_launch_args,
    get_playwright_proxy_options,
    open_rendered_page,
    rendered_html_issue,
)


def fetch_rendered_html(
    url: str,
    timeout_seconds: int,
    wait_ms: int,
    stealth_profile: int,
) -> dict[str, object]:
    """使用 Playwright 渲染页面并返回完整 HTML。"""
    from playwright.sync_api import sync_playwright

    settings = get_settings()
    warnings: list[str] = []
    with sync_playwright() as playwright:
        context = None
        browser = None
        page = None
        try:
            launch_options: dict[str, object] = {
                "headless": settings.browser_headless,
                "args": get_playwright_launch_args(stealth_profile=stealth_profile),
            }
            proxy_options = get_playwright_proxy_options()
            if proxy_options:
                launch_options["proxy"] = proxy_options
            browser = playwright.chromium.launch(**launch_options)
            context = browser.new_context(**get_browser_context_options(stealth_profile=stealth_profile))
            configure_browser_context(context, stealth_profile=stealth_profile)
            page, html, final_url = open_rendered_page(context, url, timeout_seconds, wait_ms)
            issue = rendered_html_issue(html)
            if issue:
                raise RuntimeError(f"Playwright 渲染结果疑似无效：{issue}")
            return {
                "html": html,
                "final_url": final_url,
                "warnings": warnings,
            }
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Playwright HTML 渲染助手")
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--wait-ms", type=int, required=True)
    parser.add_argument("--stealth-profile", type=int, default=1)
    return parser


def main() -> int:
    """脚本入口逻辑。"""
    argument_parser = build_parser()
    arguments = argument_parser.parse_args()
    try:
        payload = fetch_rendered_html(
            url=arguments.url,
            timeout_seconds=arguments.timeout,
            wait_ms=arguments.wait_ms,
            stealth_profile=arguments.stealth_profile,
        )
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
