from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {"rule_id": "4319", "page_type": "leader_listing", "load_mode": "http", "parser": "custom", "risk": "领导列表标题携带职务和姓名，可验证链接为人物条目。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows=[]
    for link in soup.select('.pageTPList2 a.tit[href]'):
        match=re.fullmatch(r'(.+?)[：:]([\u4e00-\u9fff]{2,4})',link.get_text(' ',strip=True))
        if match: rows.append({'name':match.group(2),'duty':match.group(1),'detail_url':urljoin(final_url,link['href'])})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
