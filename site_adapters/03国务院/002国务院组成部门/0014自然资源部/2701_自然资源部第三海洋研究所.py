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
    "rule_id": "2701",
    "page_type": "人物列表完整页",
    "structure_group": "第三海洋研究所姓名职务内容块",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "TioCurrentLeaderContentBlockParser_v2",
    "leader_region_selector": ".contentNav .rightData",
    "name_selector": ".artiTitle",
    "duty_selector": ".artiTitle后的同级div",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "原始HTTP响应直接含权威人物块，online编排所得页面状态曾缺失该块，故固定raw_http；旧详情锚点仅存在于HTML注释中，不是当前可点击链接；职务节点还包含页面原列党员和职称信息，必须完整保留；禁止固定人物映射",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _clean_duty(value: str) -> str:
    """删除当前职务节点中可确定的政治面貌和职称分句。"""
    parts = [part.strip().strip("。；") for part in re.split(r"[，,]", value) if part.strip()]
    retained = [
        part
        for part in parts
        if part not in {"中共党员", "研究员", "高级工程师", "正高级工程师"}
    ]
    return "，".join(retained).strip("；。")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按人物内容块DOM顺序动态提取姓名与完整职务节点。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for block in soup.select(".contentNav .rightData"):
        name_node = block.select_one(".artiTitle")
        duty_node = next(
            (child for child in block.find_all("div", recursive=False) if "artiTitle" not in (child.get("class") or [])),
            None,
        )
        name = _clean_text(name_node.get_text(" ", strip=True) if name_node else "").replace(" ", "")
        duty = _clean_duty(_clean_text(duty_node.get_text(" ", strip=True) if duty_node else ""))
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
                "selector_summary": ".contentNav .rightData；name=.artiTitle；duty=后续同级div；无当前人物链接",
            }
        )
    if not records:
        raise RuntimeError("领导之窗内容块未解析到人物记录")
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
