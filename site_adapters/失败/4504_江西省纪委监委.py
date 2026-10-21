from __future__ import annotations
import sys
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4504",
    "page_type": "图片型纪委监委领导名单",
    "structure_group": "jiangxi_discipline_supervision_pending_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML跳转后图片",
    "extract_mode": "custom",
    "parser": "page_jiangxi_discipline_supervision_pending_v1",
    "leader_region_selector": "最新文章正文唯一领导名单PNG",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅保留纪委书记/副书记/常委及监委主任/副主任；排除委员名单；页面无法在线核验时明确失败。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    entry = requests.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    entry.raise_for_status()
    entry_text = entry.content.decode("gb18030", errors="replace")
    redirect = re.search(r"URL=([^'\"]+)", entry_text, re.I)
    article_url = urljoin(entry.url, redirect.group(1)) if redirect else entry.url
    article = requests.get(article_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    article.raise_for_status()
    soup = BeautifulSoup(article.content.decode("gb18030", errors="replace"), "html.parser")
    image = soup.select_one("img[src*='W020'][src$='.png']")
    if image is None:
        raise RuntimeError("最新领导机构文章未发现领导名单PNG")
    image_url = urljoin(article.url, str(image.get("src") or ""))
    raise RuntimeError(f"领导名单仅承载于实时图片，当前生产运行未配置可回指视觉解析通道：{image_url}")

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
