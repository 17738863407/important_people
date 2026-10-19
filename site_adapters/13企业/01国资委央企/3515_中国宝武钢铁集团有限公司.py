from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def clean_text(value: str) -> str:
    """压缩管理团队卡片文本中的排版空白。"""
    return " ".join((value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def fetch_chrome_isolated(url: str) -> tuple[str, str]:
    """在独立 general Python 进程中取得 Chrome CDP HTML，避开当前事件循环。"""
    project_dir = resolve_project_dir()
    child_code = (
        "import base64,json,sys; "
        "sys.path.insert(0,sys.argv[2]); "
        "from crawler_core.fetcher import fetch_html_with_strategy; "
        "r=fetch_html_with_strategy(sys.argv[1],strategy='chrome',timeout=40); "
        "print(json.dumps({'html':base64.b64encode(r.html.encode('utf-8')).decode('ascii'),"
        "'final_url':r.final_url},ensure_ascii=False))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", child_code, url, str(project_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or "未知错误"
        raise RuntimeError(f"Chrome隔离子进程失败：{error}")
    output_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise RuntimeError("Chrome隔离子进程未返回页面数据")
    payload = json.loads(output_lines[-1])
    chrome_html = base64.b64decode(str(payload["html"])).decode("utf-8")
    return chrome_html, str(payload["final_url"])


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析 Chrome 渲染后的管理团队人物卡片。"""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.people-list__item")
    if not cards:
        chrome_html, final_url = fetch_chrome_isolated(final_url)
        soup = BeautifulSoup(chrome_html, "html.parser")
        cards = soup.select("li.people-list__item")
    rows: list[dict[str, str]] = []

    for card in cards:
        name_node = card.select_one(".people-list__intro h1")
        duty_node = card.select_one(".people-list__intro p")
        link_node = card.select_one("a[href]")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty:
            continue
        detail_url = urljoin(final_url, str(link_node.get("href") or "")) if link_node else ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_baowu_management_cards_v1",
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "3515",
    "page_type": "人物列表完整页",
    "structure_group": "baowu_management_team_cards",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_direct",
    "collector": "browser_dom",
    "parser": "page_inline_baowu_management_cards_v1",
    "locator_strategy": "custom_parse_page",
    "risk_flag": "requests/Playwright 只有应用空壳；解析为空时页面内置流程改用Chrome CDP取得完整管理团队卡片",
    "confidence": "high",
}


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
