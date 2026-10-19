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
    "rule_id": "1098",
    "page_type": "多人物详情合并页",
    "structure_group": "科技人才中心领导简介块",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "ItalentsAboutLeadersParser_v2",
    "leader_region_selector": "#aboutLeader .row.leader > .col-md-4",
    "name_selector": "当前人物块首个姓名文本",
    "duty_selector": "当前人物块内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物简介同时包含学历、曾任和研究领域；必须按人物块提取完整现任句，不得扫描整页或把入口页作为详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """压缩HTML排版空白，同时保留语义标点。"""
    return re.sub(r"[\s\u3000\xa0\u2002-\u200b]+", "", value).strip()


def _clean_current_evidence(value: str) -> str:
    """删除现任句固定标签和纯句末句号，保留完整任职语义。"""
    evidence = re.sub(r"^现任\s*", "", _clean_text(value))
    return re.sub(r"。$", "", evidence).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导简介块的网页顺序提取姓名与完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for block in soup.select("#aboutLeader .row.leader > .col-md-4"):
        text = _clean_text(block.get_text(" ", strip=True))
        name_match = re.match(r"^([\u4e00-\u9fff·]{2,5})[，,]", text)
        evidence_match = re.search(r"现任[^。]*。", text)
        if not name_match or not evidence_match:
            continue
        name = name_match.group(1)
        evidence = _clean_current_evidence(evidence_match.group(0))
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "#aboutLeader .row.leader > .col-md-4；块首姓名；块内完整现任句",
            }
        )
    if not records:
        raise RuntimeError("中心领导区域未解析到含完整现任句的人物记录")
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
