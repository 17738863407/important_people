"""使用无头Chromium补抓HTTP失败的省级政府机构目录。"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from tqdm import tqdm

from crawler_core.paths import resolve_project_path, timestamped_output_path


def configure_logging(log_path: Path) -> logging.Logger:
    """同时写入控制台和UTF-8日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("failed_directory_browser_render")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def safe_file_stem(index: int, label: str, url: str) -> str:
    """生成与首轮审计一致的安全文件名。"""
    clean_label = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", label).strip(" ._")
    host = urlparse(url).netloc.replace(":", "_")
    return f"{index:02d}_{clean_label}_{host}"


def main(
    targets: list[tuple[int, str, str]],
    snapshot_dir: Path,
    log_path: Path,
    timeout_milliseconds: int,
) -> None:
    """逐站渲染失败入口并保存完整DOM，单站失败不影响其他站点。"""
    logger = configure_logging(log_path)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0 Safari/537.36"
            ),
        )
        for index, label, url in tqdm(targets, desc="浏览器补抓目录", unit="站"):
            page = context.new_page()
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_milliseconds)
                page.wait_for_timeout(5000)
                html = page.content()
                output_path = snapshot_dir / f"{safe_file_stem(index, label, url)}.html"
                output_path.write_text(html, encoding="utf-8")
                status = response.status if response else "无响应对象"
                logger.info("成功：%02d %s，状态%s，最终链接%s，字符%d", index, label, status, page.url, len(html))
            except Exception:
                logger.exception("失败：%02d %s %s", index, label, url)
            finally:
                page.close()
        context.close()
        browser.close()


if __name__ == "__main__":
    targets = [
        (1, "安徽省机构", "https://www.ah.gov.cn/site/tpl/2121"),
        (6, "广东省机构", "https://www.gd.gov.cn/zwgk/szfjg/index.html"),
        (8, "贵州省机构", "https://www.guizhou.gov.cn/zwgk/zfjg/"),
        (16, "江西省机构", "https://www.jiangxi.gov.cn/jxsrmzf/szfjg/pc/list.html#szfzc"),
    ]
    snapshot_dir = resolve_project_path(r"important_people/workspace/snapshots/机构目录/省级政府机构目录/html", anchor=__file__)
    log_path = timestamped_output_path(
        resolve_project_path(
            r"important_people/workspace/log/机构目录/省级政府机构目录浏览器补抓.log",
            anchor=__file__,
        )
    )
    timeout_milliseconds = 60000
    main(targets, snapshot_dir, log_path, timeout_milliseconds)
