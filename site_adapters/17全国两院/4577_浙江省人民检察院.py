from __future__ import annotations

import sys
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4577",
    "page_type": "领导图文正文页",
    "structure_group": "zhejiang_procuratorate_profile_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "extract_mode": "custom",
    "parser": "page_zhejiang_procuratorate_profiles_v1",
    "leader_region_selector": "td.bt_content",
    "name_selector": "居中人物标题中职务标记前文本",
    "duty_selector": "当前人物块内含“现任”的简介段",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "以头像后的居中姓名职务标题分块，只在该人物块内截取现任句；委员类职务全部保留。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按实时图文块顺序抽取姓名，并在当前块内定位现任句。"""
    url = str(page_rule.get("url") or "").strip()
    if not url:
        raise RuntimeError("规则主表领导链接为空，无法在线核验领导页面")
    response = requests.get(
        url, timeout=30, verify=False,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    region = soup.select_one("td.bt_content")
    if region is None:
        raise RuntimeError("未找到领导正文区域 td.bt_content")

    role_markers = ("党组", "副检察长", "检察长", "政治部主任", "纪检监察组组长", "派驻纪检监察组组长")
    rows: list[dict[str, str]] = []
    paragraphs = region.select("p")
    for index, paragraph in enumerate(paragraphs):
        if "center" not in str(paragraph.get("style") or "").lower() or paragraph.select_one("img"):
            continue
        heading = re.sub(r"[\s\u200b\u3000\xa0]+", "", paragraph.get_text(" ", strip=True))
        positions = [heading.find(marker) for marker in role_markers if marker in heading]
        if not positions:
            continue
        role_start = min(positions)
        name = heading[:role_start].strip("：:，,、")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        duty = ""
        for following in paragraphs[index + 1:]:
            if following.select_one("img"):
                break
            text = re.sub(r"[\s\u200b\u3000\xa0]+", "", following.get_text(" ", strip=True))
            match = re.search(r"现任(.+?)(?:。|$)", text)
            if match:
                duty = match.group(1).strip("，,；;")
                break
        if not duty:
            raise RuntimeError(f"人物块缺少可验证的现任职务：{name}")
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": "",
            "parser": str(page_rule["parser"]),
            "selector_summary": "td.bt_content头像后居中标题 + 当前块现任句",
        })
    if not rows:
        raise RuntimeError("领导正文未提取到领导人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
