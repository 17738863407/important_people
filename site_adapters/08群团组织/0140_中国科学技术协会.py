from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0140",
    "page_type": "人物列表完整页",
    "structure_group": "中国科协当前领导多分组模块",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "requests",
    "parser": "CastCurrentLeaderGroupParser_v2",
    "leader_region_selector": "div.fykxld[datatype='kxld']",
    "name_selector": ".fyldle p, .fyldmd > p, .fyldmd > a",
    "duty_selector": ".fyldxm及主席卡片标题",
    "detail_link_selector": ".fyldle a[href], .fyldmd > a[href]",
    "detail_strategy": {"required": False, "mode": "person_link"},
    "risk_flag": "副主席与党组书记处分组存在跨组重复人物，需按首次顺序聚合明确分组职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def _split_name_note(value: str, base_duty: str) -> tuple[str, str]:
    text = _clean_text(value).replace(" ", "")
    match = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})(?:（([^）]+)）)?", text)
    if match is None:
        return "", ""
    name = match.group(1)
    note = match.group(2) or ""
    note_parts = [
        part.strip()
        for part in re.split(r"[，,]", note)
        if part.strip() and part.strip() != "负责日常工作"
    ]
    cleaned_note = "，".join(note_parts)
    evidence = base_duty
    if "专职" in cleaned_note:
        evidence = f"{base_duty}（{cleaned_note}）"
    return name, evidence


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按主席、副主席、党组书记处分组顺序提取并聚合唯一人物。"""
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one("div.fykxld[datatype='kxld']")
    if section is None:
        raise RuntimeError("中国科协当前领导模块不存在")
    records: list[dict] = []
    index_by_name: dict[str, int] = {}

    def append_or_merge(name: str, evidence: str, href: str = "") -> None:
        name = re.sub(r"\s+", "", name)
        evidence = _clean_text(evidence)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            return
        detail_url = urljoin(base_url, href) if href else ""
        if name in index_by_name:
            record = records[index_by_name[name]]
            parts = record["evidence"].split("；")
            if evidence not in parts:
                record["evidence"] += f"；{evidence}"
                record["duty"] = record["evidence"]
            if detail_url and not record["detail_url"]:
                record["detail_url"] = detail_url
            return
        index_by_name[name] = len(records)
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": PAGE_RULE["parser"],
                "selector_summary": "科协领导模块；按主席、副主席、党组书记处分组首次顺序聚合",
            }
        )

    chair_link = section.select_one(".fyldle a[href]")
    chair_node = chair_link.select_one("p") if chair_link else None
    if chair_link is not None and chair_node is not None:
        match = re.fullmatch(r"(.+?)\s+([\u4e00-\u9fff·]{2,5})", _clean_text(chair_node.get_text(" ", strip=True)))
        if match is not None:
            append_or_merge(match.group(2), match.group(1), str(chair_link.get("href", "")))

    for group in section.select(".fyldri li"):
        title_node = group.select_one(".fyldxm")
        if title_node is None:
            continue
        base_duty = _clean_text(title_node.get_text(" ", strip=True))
        if base_duty == "副主席":
            for name_node in group.select(".fyldmd > p"):
                name, evidence = _split_name_note(name_node.get_text(" ", strip=True), base_duty)
                append_or_merge(name, evidence)
        elif base_duty == "党组、书记处":
            for link in group.select(".fyldmd > a"):
                name, evidence = _split_name_note(link.get_text(" ", strip=True), base_duty)
                append_or_merge(name, evidence, str(link.get("href", "")))
    if not records:
        raise RuntimeError("中国科协当前领导模块未解析到人物记录")
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
