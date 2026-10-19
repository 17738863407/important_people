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
    "rule_id": "1535", "page_type": "职务分组名单页", "structure_group": "文旅部直属单位现任领导段落组", "reuse_scope": "mct_affiliated_unit_article",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "custom", "collector": "static_http", "parser": "MctAffiliatedUnitCurrentLeadersParser_v2",
    "leader_region_selector": "#zoom .TRS_Editor p", "name_selector": "现任领导与联系方式之间冒号后", "duty_selector": "现任领导与联系方式之间冒号前", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "单位简介含学术成果和奖项；必须以现任领导与联系方式标题限定人物段落", "confidence": "high", "filter_policy": "strong_no_wordlist",
}

def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()

def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    active = False
    records: list[dict] = []
    for paragraph in soup.select("#zoom .TRS_Editor p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if text == "现任领导": active = True; continue
        if active and text == "联系方式": break
        if not active: continue
        matched = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,5})", text)
        if matched: records.append({"name": matched.group(2), "duty": matched.group(1), "evidence": matched.group(1), "detail_url": "", "parser": PAGE_RULE["parser"]})
    if not records: raise RuntimeError("现任领导分组未解析到人物记录")
    return records

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
