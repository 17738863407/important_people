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
    "rule_id": "0335",
    "page_type": "职务分组名单页",
    "structure_group": "中心领导职务姓名段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CsdpDutyColonLeadersParser_v2",
    "leader_region_selector": ".main2 .m2R .m2Editor.m2Editor2",
    "name_selector": "p冒号后",
    "duty_selector": "p完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页头下拉菜单重复显示领导名单，必须只解析main2正文，防止重复；页面无人物独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按中心领导正文段落顺序抽取职务与姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".main2 .m2R .m2Editor.m2Editor2 p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:]\s*([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        name = matched.group(2)
        if name in seen_names:
            continue
        seen_names.add(name)
        duty = re.sub(r"\s+", "", matched.group(1))
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".main2 .m2R .m2Editor.m2Editor2 p；职务：姓名完整段落；排除页头下拉菜单重复名单",
            }
        )
    if not records:
        raise RuntimeError("中心领导职务姓名段落未解析到人物记录")
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
