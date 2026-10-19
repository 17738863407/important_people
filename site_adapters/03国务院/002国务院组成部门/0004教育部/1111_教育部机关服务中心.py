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
    "rule_id": "1111",
    "page_type": "人物列表完整页",
    "structure_group": "机关服务中心领导段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MoeServiceCenterLeadersParser_v2",
    "leader_region_selector": ".TRS_Editor p",
    "name_selector": "段落末尾姓名",
    "duty_selector": "段落完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "职务种类会变化，不使用固定职务前缀；按每段末尾姓名边界动态拆分，页面无人物独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u3000\xa0\u2002-\u200b]+", " ", value).strip()
    return re.sub(r"\s*([、，,；;：:（）()])\s*", r"\1", text)


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按机关服务中心领导段落顺序动态拆分职务与段尾姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".TRS_Editor p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        duty = matched.group(1)
        name = matched.group(2)
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".TRS_Editor p；段落末尾姓名边界；完整职务姓名段落证据；不固定职务前缀",
            }
        )
    if not records:
        raise RuntimeError("机关服务中心领导段落未解析到人物记录")
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
