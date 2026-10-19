from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "4540", "page_type": "法院领导简介卡片",
    "structure_group": "heilongjiang_high_court_leader_cards_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML直出", "extract_mode": "leader_cards", "parser": "page_heilongjiang_high_court_leader_cards_v1",
    "leader_region_selector": ".ldjj",
    "name_selector": ".name a[href]", "duty_selector": ".jianjie p, .jianjie-top p",
    "detail_link_selector": ".name a[href]", "detail_strategy": {"required": False, "mode": "direct_person_link"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "领导简介同时列出审判委员会委员、其他委员职务和法官等级；委员职务全部保留，组合职务仅剔除独立法官或监察官等级，法官等级为卡片唯一现职证据时保留。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".ldjj"):
        link = card.select_one(".name a[href]")
        duty_node = card.select_one(".jianjie p, .jianjie-top p")
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True) if link else "")
        raw_duty = re.sub(r"\s+", "", duty_node.get_text(" ", strip=True) if duty_node else "")
        raw_duty = re.sub(r"^现任", "", raw_duty).rstrip("。")
        parts = []
        for part in re.split(r"[，,、；;]", raw_duty):
            if not part:
                continue
            if re.search(r"[一二三四五六七八九十]级高级(?:法官|监察官)$", part):
                continue
            parts.append(part)
        evidence = "、".join(parts) or raw_duty
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": urljoin(final_url, str(link.get("href") or "")), "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".ldjj卡片按.name姓名及.jianjie职务原序提取；委员职务保留，组合职务剔除独立法官或监察官等级，唯一现职证据为法官等级时保留"})
    if not rows:
        raise RuntimeError("领导卡片未提取到有效领导职务")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
