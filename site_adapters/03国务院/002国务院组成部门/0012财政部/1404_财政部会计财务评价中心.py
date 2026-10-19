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
    "rule_id": "1404",
    "page_type": "人物列表完整页",
    "structure_group": "非法嵌套正文叶子段落职务姓名行",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofAccountingCenterLeafParagraphParser_v2",
    "leader_region_selector": "ul.contain-new p",
    "risk_flag": "必须保留当前原始HTTP正文；页面存在嵌套p汇总文本，只能解析无子p的叶子人物段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _normalize_space(value: str) -> str:
    """将全角、窄空格和不换行空格归一为单个空格。"""
    return re.sub(r"[\s\u00a0\u3000\u2002-\u200b]+", " ", str(value or "")).strip()


def _compact_name(value: str) -> str:
    """移除姓名内部的网页字距空白。"""
    return re.sub(r"\s+", "", _normalize_space(value))


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按叶子段落DOM顺序解析每行末尾姓名及前置职务。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen: set[str] = set()
    for paragraph in soup.select(rule["leader_region_selector"]):
        if paragraph.find("p") is not None:
            continue
        text = _normalize_space(paragraph.get_text(" ", strip=True))
        if not text or "现任领导" in text:
            continue
        match = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff](?:\s*[\u4e00-\u9fff·]){1,7})", text)
        if not match:
            continue
        duty = _normalize_space(match.group(1))
        name = _compact_name(match.group(2))
        if not duty or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": "ul.contain-new无子p叶子段落；末尾姓名词元",
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
