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
    "rule_id": "1624",
    "page_type": "人物列表完整页",
    "structure_group": "教育部司局领导段落",
    "reuse_scope": "moe_department_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MoeDepartmentLeadersParser_v2",
    "leader_region_selector": "#siju-section",
    "name_selector": "领导标题后TRS_Editor p前段",
    "duty_selector": "领导标题后TRS_Editor p完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同页含语言文字应用管理司介绍、内设处室、司局通知及工作专栏，必须按司领导标题选择紧邻内容块；页面无人物独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """定位领导标题的紧邻内容块，按段落顺序抽取姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    heading = next(
        (
            node
            for node in soup.select("#siju-section .siju-lanmu h2")
            if "领导" in _clean_text(node.get_text(" ", strip=True))
        ),
        None,
    )
    container = heading.parent.find_next_sibling("div") if heading and heading.parent else None
    if container is None:
        raise RuntimeError("司局页面未找到领导标题的紧邻内容块")

    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in container.select(".TRS_Editor p"):
        raw_evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"([\u4e00-\u9fff·](?:\s*[\u4e00-\u9fff·]){1,4})\s+(.+)", raw_evidence)
        if not matched:
            continue
        name = re.sub(r"\s+", "", matched.group(1))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        evidence = matched.group(2).strip()
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "#siju-section；含领导的h2；紧邻lanmu-neirong TRS_Editor p；姓名+职务完整段落",
            }
        )
    if not records:
        raise RuntimeError("司局领导内容块未解析到人物记录")
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
