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
    "rule_id": "4263",
    "page_type": "现任领导详情正文",
    "structure_group": "中国医学气功学会现任领导职务姓名标题段落",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_cmqg_leaders_v1",
    "leader_region_selector": ".static-page",
    "name_selector": "p",
    "duty_selector": "人物简介前的职务姓名标题段落",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面是连续人物简介，必须只读取以领导职务开头的标题段落，不能把履历、曾任或其他协会职务混入。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """从现任领导人物简介前的标题段落读取姓名和学会职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r"^(名誉会长|副秘书长|秘书长|副会长|会长)([\u4e00-\u9fff·]{2,8})$")
    for paragraph in soup.select(".static-page > p"):
        text = re.sub(r"\s+", "", paragraph.get_text(" ", strip=True))
        matched = pattern.fullmatch(text)
        if not matched:
            continue
        duty, name = matched.groups()
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "parser": page_rule["parser"],
                "selector_summary": ".static-page人物简介前的职务姓名标题段落",
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
