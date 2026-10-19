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
    "rule_id": "1830",
    "page_type": "人物目录详情页",
    "structure_group": "同段落换行领导名单",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NatcmLineSeparatedLeaderParagraphParser_v2",
    "leader_region_selector": "span.zw p",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "多名领导位于同一段落的独立换行文本中，必须逐行解析并保持换行顺序",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落内部换行文本顺序抽取人事教育司领导。"""
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(
        r"^(?P<name>[\u4e00-\u9fff](?:\s*[\u4e00-\u9fff]){1,3})\s+"
        r"(?P<duty>人事教育司.+)$"
    )
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select("span.zw p"):
        for source_line in paragraph.stripped_strings:
            evidence = _clean_text(source_line)
            match = pattern.fullmatch(evidence)
            if not match:
                continue
            name = re.sub(r"\s+", "", match.group("name"))
            if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen_names:
                continue
            seen_names.add(name)
            duty = _clean_text(match.group("duty"))
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": "span.zw p；段内换行文本；人事教育司职务",
                }
            )
    if not records:
        raise RuntimeError("领导正文未解析到人事教育司人物行")
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
