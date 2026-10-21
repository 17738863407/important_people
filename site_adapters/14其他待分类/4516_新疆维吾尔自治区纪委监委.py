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
    "rule_id": "4516",
    "page_type": "纪委监委领导机构页面待核验",
    "structure_group": "xinjiang_discipline_supervision_pending_v1",
    "reuse_scope": "single_page",
    "load_mode": "在线页面待核验",
    "extract_mode": "custom",
    "parser": "page_xinjiang_discipline_supervision_pending_v1",
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
    """实际尝试在线访问；失败时拒绝猜测页面结构或人物结果。"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36", "Accept": "text/html,application/xhtml+xml", "Referer": "https://www.xjjw.gov.cn/"}
    response = requests.get(str(page_rule["url"]), timeout=30, verify=False, headers=headers)
    response.raise_for_status(); response.encoding = "utf-8"
    region = BeautifulSoup(response.text, "html.parser").select_one(".show-content")
    if region is None: raise RuntimeError("领导机构页缺少 .show-content")
    people: OrderedDict[str, list[str]] = OrderedDict(); section = ""
    name_re = re.compile(r"[\u3400-\u9fff]{2,8}·\s*[\u3400-\u9fff]{2,8}|[\u3400-\u9fff]{2,4}")
    for paragraph in region.select("p"):
        text = paragraph.get_text(" ", strip=True).replace("\xa0", " ")
        compact = re.sub(r"\s+", "", text)
        if compact.startswith("中国共产党新疆维吾尔自治区") and compact.endswith("纪律检查委员会"):
            section = compact; continue
        if compact == "新疆维吾尔自治区监察委员会": section = compact; continue
        match = re.match(r"\s*(书\s*记|副\s*书\s*记|常务委员会委员|代\s*主\s*任|主\s*任|副\s*主\s*任)\s+(.+)", text)
        if match is None: continue
        role = re.sub(r"\s+", "", match.group(1)); remainder = re.sub(r"[（(][^）)]*[）)]", "", match.group(2))
        for raw_name in name_re.findall(remainder):
            name = re.sub(r"\s+", "", raw_name); duties = people.setdefault(name, []); duty = section + role
            if duty not in duties: duties.append(duty)
    rows = [{"name": n, "duty": "；".join(ds), "evidence": "；".join(ds), "detail_url": "", "parser": str(page_rule["parser"]), "selector_summary": ".show-content纪委监委目标职务行"} for n, ds in people.items()]
    if not rows: raise RuntimeError("目标职务行未提取到人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
