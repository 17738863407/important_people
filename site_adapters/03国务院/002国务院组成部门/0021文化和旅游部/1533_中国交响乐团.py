from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1533",
    "page_type": "职务分组名单页",
    "structure_group": "文旅部直属单位现任领导div文本流",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MctSymphonyCurrentLeadersParser_v2",
    "leader_region_selector": "#zoom .TRS_Editor",
    "name_selector": "独立现任领导标题后、联系方式前文本节点冒号后",
    "duty_selector": "独立现任领导标题后、联系方式前文本节点冒号前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "单位简介含大量历任艺术家、荣誉指挥和当前领导汇总句；必须从独立现任领导标题后的div文本流解析，避免混入或重复",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """沿独立“现任领导”标题后的文本流解析领导名单。"""
    soup = BeautifulSoup(html, "html.parser")
    editor = soup.select_one("#zoom .TRS_Editor")
    if editor is None:
        raise RuntimeError("未找到中国交响乐团正文")
    heading_text = next((text for text in editor.find_all(string=True) if _clean_text(str(text)) == "现任领导"), None)
    if heading_text is None:
        raise RuntimeError("正文未找到独立现任领导标题")
    records: list[dict] = []
    seen_names: set[str] = set()
    for element in heading_text.next_elements:
        if not isinstance(element, NavigableString):
            continue
        evidence = _clean_text(str(element))
        if evidence == "联系方式":
            break
        matched = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        duty, name = matched.groups()
        if name in seen_names:
            continue
        seen_names.add(name)
        records.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": PAGE_RULE["parser"], "selector_summary": "#zoom .TRS_Editor；独立现任领导标题后文本流；联系方式前；职务：姓名"})
    if not records:
        raise RuntimeError("现任领导文本流未解析到人物记录")
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
