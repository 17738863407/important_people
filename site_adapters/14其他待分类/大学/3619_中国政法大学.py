from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PAGE_RULE = {
    "rule_id": "3619",
    "domain": "www.cupl.edu.cn",
    "page_type": "人物卡片分组页",
    "structure_group": "cupl_dynamic_challenge_2026",
    "reuse_scope": "single_page",
    "load_mode": "公开动态挑战后静态HTML",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "custom_parse_page",
    "collector": "custom_http_session",
    "parser": "page_cupl_leader_cards_after_challenge_v2",
    "leader_region_selector": ".xrld",
    "name_selector": ".xrld li h3末尾姓名",
    "duty_selector": ".xrld li h3姓名前职务",
    "detail_link_selector": ".xrld li a[href]",
    "detail_strategy": {"required": False, "mode": "from_list"},
    "risk_flag": "党委和行政分组重复展示校长，按姓名保留首次出现记录",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}

def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    """清理卡片标题中的排版空白。"""
    return re.sub(r"\s+", " ", value or "").strip()


def fetch_verified_page(entry_url: str) -> tuple[str, str]:
    """完成官网公开的动态挑战，返回真实领导页面HTML和最终网址。"""
    session = requests.Session()
    session.trust_env = False
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
    )
    headers = {"User-Agent": user_agent}
    response = session.get(entry_url, headers=headers, timeout=25)
    response.raise_for_status()
    response.encoding = "utf-8-sig"

    challenge_id = re.search(r'challengeId\s*=\s*"(?P<value>[^"]+)"', response.text)
    challenge_answer = re.search(r"answer\s*=\s*(?P<value>\d+)", response.text)
    if challenge_id is not None or challenge_answer is not None:
        if challenge_id is None or challenge_answer is None:
            raise RuntimeError("动态挑战参数不完整")
        payload = {
            "challenge_id": challenge_id.group("value"),
            "answer": int(challenge_answer.group("value")),
            "browser_info": {
                "userAgent": user_agent,
                "language": "zh-CN",
                "platform": "Win32",
                "cookieEnabled": True,
                "hardwareConcurrency": 0,
                "deviceMemory": 0,
                "timezone": "Asia/Shanghai",
            },
        }
        challenge_response = session.post(
            urljoin(response.url, "/dynamic_challenge"),
            json=payload,
            headers={**headers, "Referer": response.url},
            timeout=25,
        )
        challenge_response.raise_for_status()
        if not challenge_response.json().get("success"):
            raise RuntimeError("动态挑战验证未成功")
        response = session.get(entry_url, headers=headers, timeout=25)
        response.raise_for_status()
        response.encoding = "utf-8-sig"

    if "challengeId" in response.text or not response.text.strip():
        raise RuntimeError("动态挑战后仍未取得真实领导页面")
    return response.text, response.url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析官网现任领导卡片，按DOM顺序对跨分组重复人物去重。"""
    del html, final_url
    page_html, page_url = fetch_verified_page(str(page_rule.get("url", "")))
    soup = BeautifulSoup(page_html, "html.parser")
    cards = soup.select(".xrld li")
    if not cards:
        raise RuntimeError("动态挑战后页面未找到 .xrld 领导卡片")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    title_pattern = re.compile(
        r"^(?P<evidence>.+?)\s+(?P<name>[\u3400-\u9fff·]{2,4})$"
    )
    for card in cards:
        title_node = card.select_one("h3")
        link_node = card.select_one("a[href]")
        if title_node is None:
            continue
        title = clean_text(title_node.get_text(" ", strip=True))
        match = title_pattern.fullmatch(title)
        if match is None:
            continue
        name = match.group("name")
        evidence = clean_text(match.group("evidence"))
        if name in seen_names or not evidence:
            continue
        seen_names.add(name)
        href = str(link_node.get("href", "")).strip() if link_node is not None else ""
        detail_url = urljoin(page_url, href) if href else ""
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": ".xrld li；h3姓名前职务；按姓名首次出现去重",
            }
        )
    return rows


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
