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
    "rule_id": "1629",
    "page_type": "人物列表完整页",
    "structure_group": "教育部驻部纪检监察组职务姓名段落",
    "reuse_scope": "moe_discipline_inspection_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MoeDisciplineInspectionLeadersParser_v2",
    "leader_region_selector": ".section-jijianzu dl",
    "name_selector": "组领导dd .TRS_Editor p冒号后文本",
    "duty_selector": "组领导dd .TRS_Editor p完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面与教育部司局页结构不同，人物段落采用职务在前、姓名在后的冒号格式；必须限定dt为组领导的dl，排除机构设置及页脚",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """限定“组领导”分组，按段落顺序解析冒号后的姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_group = next(
        (
            group
            for group in soup.select(".section-jijianzu dl")
            if group.find("dt") and _clean_text(group.find("dt").get_text(" ", strip=True)) == "组领导"
        ),
        None,
    )
    if leader_group is None:
        raise RuntimeError("驻部纪检监察组页面未找到组领导分组")

    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in leader_group.select("dd .TRS_Editor p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:]\s*([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        duty = matched.group(1).strip()
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
                "selector_summary": ".section-jijianzu；dt=组领导；同dl dd .TRS_Editor p；职务：姓名完整段落",
            }
        )
    if not records:
        raise RuntimeError("组领导分组未解析到人物记录")
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
