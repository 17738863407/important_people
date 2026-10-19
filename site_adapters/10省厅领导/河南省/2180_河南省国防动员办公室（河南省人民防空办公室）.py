from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "2180",
    "page_type": "人物列表完整页",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "页面内置parse_page",
    "leader_region_selector": ".leaderlist",
    "row_selector": ".leaderlist .leaderitem",
    "name_selector": "详情页h1",
    "duty_selector": ".leaderitem .fgtext中详情姓名前文本",
    "detail_link_selector": ".leaderitem a.leaderpic[href]",
    "filter_strategy": "strong_no_wordlist",
    "confidence": "high",
    "risk": "列表职务、姓名与人口学信息连续展示且HTML注释含重复旧节点；姓名须由对应详情页h1动态核验后再切分列表文本。",
}


def normalize_text(text: str) -> str:
    """仅压缩字段中的排版空白。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()


def normalize_name(text: str) -> str:
    """去除姓名中的排版空格。"""
    return re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", "", str(text or "")).strip()


def load_detail_name(url: str) -> tuple[str, str]:
    """在线读取详情页并以h1核验人物姓名。"""
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "html.parser")
    heading = soup.select_one("h1")
    name = normalize_name(heading.get_text(" ", strip=True)) if heading else ""
    return name, response.url.replace(":443/", "/")


def parse_page(html: str, base_url: str, rule: dict[str, object]) -> list[dict[str, str]]:
    """按领导卡片顺序以详情页姓名切分列表中的完整职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []

    for card in soup.select(".leaderlist .leaderitem"):
        link = card.select_one("a.leaderpic[href]")
        text_node = card.select_one(".fgtext")
        if link is None or text_node is None:
            continue
        requested_url = urljoin(base_url, str(link.get("href") or ""))
        try:
            name, detail_url = load_detail_name(requested_url)
        except requests.RequestException:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name):
            continue

        profile_text = normalize_text(text_node.get_text(" ", strip=True))
        if name not in profile_text:
            continue
        duty = profile_text.split(name, 1)[0].strip("：:，,。；; ")
        if not duty:
            continue

        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": f"{duty}{name}",
            }
        )

    return rows


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
