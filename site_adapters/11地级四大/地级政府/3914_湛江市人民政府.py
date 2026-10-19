from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3914",
    "page_type": "侧栏人物目录与当前详情",
    "structure_group": "zhanjiang_government_sidebar_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_zhanjiang_government_sidebar_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".sideBar .li1",
    "name_selector": ".a1文本末尾姓名",
    "duty_selector": ".a1文本姓名前职务",
    "detail_link_selector": ".a1[href]",
    "risk_flag": "正文仅展示当前选中人物；完整目录位于独立侧栏",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按侧栏目录原始顺序提取职务、姓名和人物详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in soup.select(".sideBar .li1 > a.a1[href]"):
        label = clean_text(link.get_text(" ", strip=True))
        label_match = re.fullmatch(r"(.*?(?:市长|秘书长))\s+([\u3400-\u9fff·]{2,20})", label)
        if label_match is None:
            continue
        duty = clean_text(label_match.group(1))
        name = label_match.group(2)
        href = clean_text(link.get("href"))
        detail_url = urljoin(base_url, href) if href else ""
        if name in seen_names or urlparse(detail_url).scheme not in {"http", "https"}:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": ".sideBar .li1 > a.a1人物目录",
            }
        )

    if not rows:
        raise RuntimeError("侧栏人物目录未提取到有效领导")
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

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
