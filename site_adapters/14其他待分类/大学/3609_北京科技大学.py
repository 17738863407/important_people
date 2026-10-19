from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {"rule_id": "3609", "domain": "www.ustb.edu.cn", "page_type": "现任领导职务分组",
    "structure_group": "ustb_now_leaders_2026", "reuse_scope": "single_page", "load_mode": "静态HTML直出",
    "fetch_mode": "online", "extract_mode": "grouped_strong_names_merge", "collector": "static_http",
    "parser": "page_ustb_current_leaders_v1", "leader_region_selector": ".now_leaders", "name_selector": ".name01 strong",
    "duty_selector": ".job01", "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "current_region_only_merge_duties", "confidence": "high", "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page"}


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean(text: str) -> str:
    """删除纯排版空白。"""
    return re.sub(r"\s+", "", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip("：:")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导分组顺序提取并合并同一人物多项职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".now_leaders")
    if region is None: return []
    store: dict[str, list[str]] = {}
    for group in region.select(".leader_info"):
        duty_node = group.select_one(":scope > span > .job01")
        names_node = group.select_one(":scope > span > .name01")
        duty = clean(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not duty or names_node is None: continue
        for node in names_node.select(":scope > strong"):
            name = clean(node.get_text(" ", strip=True))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name): continue
            duties = store.setdefault(name, [])
            if duty not in duties: duties.append(duty)
    return [{"name": name, "duty": "；".join(duties), "evidence": "；".join(duties), "detail_url": "",
             "parser": str(page_rule.get("parser", "")),
             "selector_summary": "strategy=custom_parse_page；region=.now_leaders；group=.leader_info；fields=.job01+.name01 strong；duties=merged"}
            for name, duties in store.items()]


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(PAGE_RULE, globals(), runtime_context=runtime_context, update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
