from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4331",
    "page_type": "leader_text_list",
    "load_mode": "http",
    "parser": "custom",
    "risk": "总商会领导班子正文按职务标题与顿号分隔姓名列示，未提供人物详情页。",
    "confidence": "medium",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, str]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for paragraph in soup.select("ul.a_content > p"):
        text = re.sub(r"[\s\u00a0\u3000]+", "", paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"(会长|副会长|秘书长)[：:](.+)", text)
        if not match:
            continue
        for name in re.split(r"[、，,]", match.group(2)):
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                rows.append({"name": name, "duty": match.group(1), "detail_url": ""})
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
