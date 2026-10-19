from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id": "4316", "page_type": "article_role_name_pairs", "load_mode": "http", "parser": "custom", "risk": "实时名单正文按职务：姓名逐行发布，无独立人物页。", "confidence": "high"}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select(".zhengwen p"):
        text = re.sub(r"[\s　]+", "", paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff]{2,4})", text)
        if match:
            rows.append({"name": match.group(2), "duty": match.group(1), "detail_url": ""})
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
