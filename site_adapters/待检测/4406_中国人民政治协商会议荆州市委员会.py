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


PAGE_RULE = {
    "rule_id": "4406",
    "page_type": "current_committee_leadership_articles",
    "load_mode": "http",
    "fetch_mode": "raw_http",
    "parser": "custom",
    "risk": "机构设置页同时列出历届名单、委员和专委会；仅读取第六届主席、副主席、秘书长、副秘书长四篇现行文章。",
    "confidence": "high",
}


def _request_text(url: str) -> str:
    import requests

    session = requests.Session()
    session.trust_env = False
    response = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _duty_from_title(title: str) -> str:
    for duty in ("副秘书长", "秘书长", "副主席", "主席"):
        if title.endswith(duty):
            return duty
    return ""


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """逐篇读取第六届领导名单，按文章顺序展开职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for link in soup.select('a[title^="政协荆州市第六届委员会"][href]'):
        title = link.get("title", "").strip()
        duty = _duty_from_title(title)
        if not duty:
            continue
        detail_url = urljoin(final_url, link["href"])
        detail = BeautifulSoup(_request_text(detail_url), "html.parser")
        content = detail.select_one(".view")
        if content is None:
            continue
        names: list[str] = []
        for node in content.find_all("p", recursive=False):
            name = re.sub(r"\s+", "", node.get_text(" ", strip=True))
            if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name):
                names.append(name)
        person_detail_url = detail_url if len(names) == 1 else ""
        for name in names:
            rows.append({"name": name, "duty": duty, "detail_url": person_detail_url})
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
