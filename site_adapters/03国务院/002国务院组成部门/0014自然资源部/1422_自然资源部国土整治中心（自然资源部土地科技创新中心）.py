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
    "rule_id": "1422",
    "page_type": "人物列表完整页",
    "structure_group": "国土整治中心姓名冒号职务段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "LcrcCenterLeaderParagraphParser_v2",
    "leader_region_selector": ".div-right-con .TRS_Editor",
    "name_selector": "p冒号前文本",
    "duty_selector": "p冒号后文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名与职务含全角空格等排版字符；当前段落无人物链接，不得把入口页写入详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ").replace("\xa0", " ")).strip()


def _parse_name_duty(value: str) -> tuple[str, str]:
    matched = re.fullmatch(r"(.+?)[：:](.+)", _normalize_space(value))
    if not matched:
        return "", ""
    name = re.sub(r"\s+", "", matched.group(1))
    duty = _normalize_space(matched.group(2))
    duty = re.sub(r"(?<=[、，,])\s+(?=[\u4e00-\u9fff])", "", duty).strip(" ：:，,。.")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return "", ""
    return name, duty


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文段落顺序解析冒号两侧姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".div-right-con .TRS_Editor")
    if region is None:
        raise RuntimeError("未找到中心领导正文区域")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        name, duty = _parse_name_duty(paragraph.get_text(" ", strip=True))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".div-right-con .TRS_Editor p；姓名：职务；无人物链接",
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
