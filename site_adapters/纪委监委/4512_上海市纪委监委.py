from __future__ import annotations

import re
import sys
from collections import OrderedDict
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
    "rule_id": "4512",
    "page_type": "纪委监委领导机构页面待核验",
    "structure_group": "shanghai_discipline_supervision_pending_v1",
    "reuse_scope": "single_page",
    "load_mode": "在线页面待核验",
    "extract_mode": "custom",
    "parser": "page_shanghai_discipline_supervision_pending_v1",
    "leader_region_selector": "未经实时页面核验，不猜测选择器",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "low",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "执行环境禁止出站连接，未取得可验证页面结构；禁止使用历史名单或猜测解析规则。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status(); response.encoding = "utf-8"
    region = BeautifulSoup(response.text, "html.parser").select_one("#ivs_content")
    if region is None: raise RuntimeError("领导机构正文缺少 #ivs_content")
    people: OrderedDict[str, list[str]] = OrderedDict(); section = ""; pending = ""
    for paragraph in region.select("p"):
        text = paragraph.get_text(" ", strip=True).replace("\xa0", " ")
        compact = re.sub(r"\s+", "", text)
        if "纪律检查委员会" in compact and "委员（" not in compact:
            section = compact; continue
        strong = paragraph.find("strong")
        raw_role = strong.get_text(" ", strip=True) if strong else ""
        role_text = re.sub(r"\s+", "", raw_role).rstrip("：:")
        if "委员" in role_text and role_text != "常委": break
        role = {"书记": "书记", "副书记": "副书记", "常委": "常务委员会委员"}.get(role_text, pending)
        if not role: continue
        remainder = text.replace(raw_role, "", 1) if strong else text
        names = re.findall(r"[\u3400-\u9fff]{2,4}", re.sub(r"[（(][^）)]*[）)]", "", remainder))
        if not names: pending = role; continue
        pending = ""
        for name in names:
            duties = people.setdefault(name, []); duty = section + role
            if duty not in duties: duties.append(duty)
    rows = [{"name": n, "duty": "；".join(ds), "evidence": "；".join(ds), "detail_url": "", "parser": str(page_rule["parser"]), "selector_summary": "#ivs_content纪委目标职务段"} for n, ds in people.items()]
    if not rows: raise RuntimeError("纪委目标职务段未提取到人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
