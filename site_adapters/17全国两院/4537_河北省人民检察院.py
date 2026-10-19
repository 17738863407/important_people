from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4537", "page_type": "省检察院领导图文介绍页",
    "structure_group": "hebei_procuratorate_strong_pairs_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_hebei_procuratorate_strong_pairs_v1",
    "leader_region_selector": "#fontzoom", "name_selector": "正文strong姓名", "duty_selector": "姓名后strong职务",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"}, "locator_strategy": "custom_parse_page",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "领导介绍正文内的检察委员会委员、专职委员及其他领导人物全部保留。",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("#fontzoom")
    if region is None:
        raise RuntimeError("未找到领导介绍正文 #fontzoom")
    rows: list[dict[str, str]] = []
    pending_name = ""
    for strong in region.find_all("strong"):
        text = compact(strong.get_text(" ", strip=True))
        if not text:
            continue
        if re.fullmatch(r"[\u3400-\u9fff·]{2,6}", text):
            pending_name = text
            continue
        if not pending_name:
            continue
        if any(keyword in text for keyword in ("检察长", "纪检监察组组长", "政治部主任", "检察委员会", "专职委员")):
            evidence = "河北省人民检察院" + re.sub(r"[，,]", "、", text)
            rows.append({"name": pending_name, "duty": evidence, "evidence": evidence, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "#fontzoom strong姓名—职务配对；保留全部委员职务"})
        pending_name = ""
    if not rows:
        raise RuntimeError("未提取到省院领导区域人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")


if __name__ == "__main__":
    main()
