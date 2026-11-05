from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4326",
    "page_type": "leader_page",
    "load_mode": "http",
    "parser": "custom",
    "leader_region_selector": ".ldzc-list .leader-item",
    "name_selector": "dt h4 a[href]",
    "duty_selector": ".infos中label为领导职务的.text",
    "risk": "领导列表有分页，须按当前createPageHTML参数读取全部页且排除工作分工。",
    "confidence": "high",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    """按当前分页参数逐页读取领导卡片的姓名、完整职务和人物链接。"""
    import re
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    if "知道创宇云防御" in html or "客户端特征" in html:
        raise RuntimeError("在线入口页被知道创宇WAF拦截，未返回领导信息页面")
    pagination = re.search(r'''createPageHTML\(\s*["']page_div["']\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*["']([\w-]+)["']\s*,\s*["'](\w+)["']\s*,\s*(\d+)\s*\)''', html)
    if pagination is None:
        raise RuntimeError("未取得领导列表的完整分页参数")
    pages, current, prefix, suffix, total = pagination.groups()
    if int(current) != 1 or not 1 <= int(pages) <= 50:
        raise RuntimeError("领导列表当前页码或总页数异常")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for number in range(1, int(pages) + 1):
        if number == 1:
            page_html, page_url = html, final_url
        else:
            result = fetch_html_with_strategy(urljoin(final_url, f"{prefix}_{number}.{suffix}"), strategy="raw_http", timeout=30)
            page_html, page_url = result.html, result.final_url
        soup = BeautifulSoup(page_html, "html.parser")
        for card in soup.select(".ldzc-list .leader-item"):
            if any(n.has_attr("hidden") or n.get("aria-hidden") == "true" or "display:none" in str(n.get("style", "")).replace(" ", "") for n in [card, *card.parents]):
                continue
            link = card.select_one("dt h4 a[href]")
            name = "".join(link.get_text(" ", strip=True).split()) if link else ""
            evidence = ""
            for field in card.select("dd > .infos"):
                label, value = field.select_one("label"), field.select_one(".text")
                if label and value and label.get_text(" ", strip=True).rstrip("：:") == "领导职务":
                    evidence = " ".join(value.get_text(" ", strip=True).split())
                    break
            if not name or not evidence or name in seen:
                raise RuntimeError("领导卡片姓名职务缺失或跨页重复")
            seen.add(name)
            rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": urljoin(page_url, str(link["href"]))})
    if len(rows) != int(total):
        raise RuntimeError(f"领导列表分页数量不完整：{len(rows)}/{total}")
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
