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
    "rule_id": "0520",
    "page_type": "多人物详情合并页",
    "structure_group": "现任领导合并卡片",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "EqeaCurrentLeaderItemsParser_v2",
    "leader_region_selector": ".current-leader-list .current-leader-item",
    "name_selector": "卡片文本首段",
    "duty_selector": "卡片完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "必须限定current-leader-list，避免左侧历任领导入口和页面其他人物；卡片无个人详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s*([、，,；;：:（）()])\s*", r"\1", text)


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按现任领导合并卡片DOM顺序抽取人物与完整证据。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for item in soup.select(".current-leader-list .current-leader-item"):
        evidence = _clean_text(item.get_text(" ", strip=True))
        matched = re.fullmatch(r"([\u4e00-\u9fff·\s]{2,8})(中心.+)", evidence)
        if not matched:
            continue
        name = re.sub(r"\s+", "", matched.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        seen_names.add(name)
        duty = _clean_text(matched.group(2))
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".current-leader-list .current-leader-item；姓名为中心前文本；完整卡片原文证据；无个人详情链接",
            }
        )
    if not records:
        raise RuntimeError("现任领导合并卡片未解析到人物记录")
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
