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
    "rule_id": "1591",
    "page_type": "人物列表完整页",
    "structure_group": "正文图片下方职务姓名分组行",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MiitIcdcVsbLeaderGroupLineParser_v2",
    "leader_region_selector": "#vsb_content",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "副主任3人共用同一分组段落，需为每人保留完整连续原文证据",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导正文段落顺序拆分职务姓名，并保留完整分组段落证据。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#vsb_content")
    if region is None:
        raise RuntimeError("未找到领导正文 #vsb_content")

    rows: list[dict] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matches = re.findall(r"(?P<duty>副?主任)\s+(?P<name>[\u4e00-\u9fff]{2,4})", evidence)
        for duty, name in matches:
            if name in seen:
                continue
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": "#vsb_content p；职务姓名分组行",
                }
            )

    if not rows:
        raise RuntimeError("领导正文未解析到职务姓名记录")
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
