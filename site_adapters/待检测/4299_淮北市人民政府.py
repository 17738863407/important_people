from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4299", "page_type": "javascript_leader_cards", "load_mode": "http", "parser": "custom", "risk": "规则入口默认打开市委页；从其可验证的市政府标签进入，并解析页面公开脚本加载的卡片。", "confidence": "high"}


def _government_html(html: str, base_url: str) -> tuple[str, str]:
    """跟随入口页中唯一的市政府领导标签，避免把市委领导作为市政府结果。"""
    from bs4 import BeautifulSoup
    import requests

    soup = BeautifulSoup(html, "html.parser")
    link = next((a for a in soup.select(".ld-tit a[href]") if a.get_text(" ", strip=True) == "市政府领导"), None)
    if link is None:
        return "", base_url
    session = requests.Session()
    session.trust_env = False
    target = urljoin(base_url, link["href"])
    response = session.get(target, headers={"User-Agent": "Mozilla/5.0"}, timeout=25, verify=False)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text, response.url


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    """按市政府页三组卡片脚本的声明顺序读取姓名、职务和个人栏目链接。"""
    from bs4 import BeautifulSoup
    import requests

    government_html, government_url = _government_html(html, final_url)
    government = BeautifulSoup(government_html, "html.parser")
    session = requests.Session()
    session.trust_env = False
    rows: list[dict[str, str]] = []
    for script in government.select(".leader-type .leader-main script[src]"):
        response = session.get(urljoin(government_url, script["src"]), headers={"User-Agent": "Mozilla/5.0"}, timeout=25, verify=False)
        response.raise_for_status()
        for fragment in re.findall(r"linkLi\s*=\s*'(.*?)';", response.text, flags=re.S):
            card = BeautifulSoup(fragment, "html.parser")
            link = card.select_one("a[href]")
            name_node = card.select_one(".name")
            duty_node = card.select_one(".img_title p")
            if link and name_node and duty_node:
                duty = "；".join(duty_node.stripped_strings)
                rows.append({
                    "name": re.sub(r"[\s　]+", "", name_node.get_text(" ", strip=True)),
                    "duty": duty,
                    "detail_url": urljoin(government_url, link["href"]),
                })
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
