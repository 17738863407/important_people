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
    "rule_id": "2721",
    "page_type": "人物列表完整页",
    "structure_group": "gx_stats_profile_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "builtin_parse_page",
    "leader_region_selector": ".listrds_bmt",
    "name_selector": ".listrds_bmt > div p",
    "duty_selector": ".listrds_bmt > div p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面同时保留旧HTML注释与当前可见人物块；仅解析可见块内姓名（职务）段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ").replace("\u2002", " ")
    return re.sub(r"\s+", "", text).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按当前可见人物块顺序提取“姓名（职务）”标题段。"""
    from bs4 import BeautifulSoup

    del final_url, page_rule
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in soup.select(".listrds_bmt > div"):
        match = None
        for paragraph in block.select("p"):
            text = _compact_text(paragraph.get_text(" ", strip=True))
            match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})（([^（）]{1,80})）", text)
            if match is not None:
                break
        if match is None:
            continue
        name, duty = match.group(1), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
            }
        )

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
