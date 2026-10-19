from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1889",
    "page_type": "人物分组卡片页",
    "structure_group": "可见职务容器与成员卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ZhengzhouCppccVisibleLeaderGroupParser_v2",
    "leader_region_selector": ".position",
    "name_selector": ".leader-name, .member-name",
    "risk_flag": "HTML注释含旧空职务组，人物锚点均为#而非详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """仅归一页面排版空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def _clean_name(value: str) -> str:
    """姓名字段仅去除排版空白。"""
    return "".join(_clean_text(value).split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按可见职务容器顺序解析成员，自动排除HTML注释内容。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for title in soup.select(rule["leader_region_selector"]):
        evidence = _clean_text(title.get_text(" ", strip=True))
        container = title.parent
        if not evidence or container is None:
            continue
        for name_node in container.select(rule["name_selector"]):
            name = _clean_name(name_node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen:
                continue
            seen.add(name)
            records.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": "",
                    "parser": rule["parser"],
                    "selector_summary": ".position职务标题所在可见容器内leader/member-name",
                }
            )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
