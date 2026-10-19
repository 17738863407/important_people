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
    "rule_id": "1084",
    "page_type": "人物列表完整页",
    "structure_group": "科技部信息中心领导行",
    "reuse_scope": "most_information_center_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MostInformationCenterLeadersParser_v2",
    "leader_region_selector": ".jfjg_zxld",
    "name_selector": "p.row去除.jfjg_zxlds职务后的行尾文本",
    "duty_selector": ".jfjg_zxlds",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导模块紧邻机构设置与联系方式，必须限定.jfjg_zxld p.row；职务和姓名含用于对齐的多种Unicode空白，人物无独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2002-\u200b]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按中心领导行顺序解析职务节点与行尾姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select(".jfjg_zxld p.row"):
        duty_node = paragraph.select_one(".jfjg_zxlds")
        duty = _compact_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        full_text = _compact_text(paragraph.get_text(" ", strip=True))
        name = full_text.removeprefix(duty)
        if duty not in {"主任", "副主任"}:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".jfjg_zxld p.row；.jfjg_zxlds职务+去除对齐空白后的行尾姓名",
            }
        )
    if not records:
        raise RuntimeError("中心领导模块未解析到人物记录")
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
