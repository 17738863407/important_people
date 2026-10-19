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
    "rule_id": "1410",
    "page_type": "人物列表完整页",
    "structure_group": "国土卫星中心姓名强标记职务文本块",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "LasacCenterLeaderTextBlockParser_v2",
    "leader_region_selector": ".bottom_right",
    "name_selector": ".right_text strong",
    "duty_selector": ".right_text strong之后的文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "原始HTTP响应直接含权威领导块，online编排所得页面状态曾缺失该块，故固定raw_http；姓名含不换行空格等排版字符；当前文本块无人物链接，不得把入口页写入详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _duty_after_name(name_node) -> str:
    parts: list[str] = []
    for sibling in name_node.next_siblings:
        if isinstance(sibling, str):
            parts.append(sibling)
        elif getattr(sibling, "get_text", None):
            parts.append(sibling.get_text(" ", strip=True))
    return _normalize_space(" ".join(parts)).strip(" ：:，,。.")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按姓名强标记及其后文本提取中心领导。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".bottom_right")
    if region is None:
        raise RuntimeError("未找到中心领导正文区域")
    records: list[dict] = []
    seen_names: set[str] = set()
    for block in region.select(".right_text"):
        name_node = block.select_one("strong")
        if name_node is None:
            continue
        name = re.sub(r"\s+", "", _normalize_space(name_node.get_text(" ", strip=True)))
        duty = _duty_after_name(name_node)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".bottom_right .right_text；name=strong；duty=strong后续文本；无人物链接",
            }
        )
    if not records:
        raise RuntimeError("中心领导正文未解析到人物记录")
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
