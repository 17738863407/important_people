from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4508",
    "page_type": "纪委监委双子页分组名单",
    "structure_group": "qinghai_discipline_supervision_subpages_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态主页面加双子页",
    "extract_mode": "custom",
    "parser": "page_qinghai_discipline_supervision_pending_v1",
    "leader_region_selector": ".submenu目标子页及其正文",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "执行环境禁止出站连接，未取得可验证页面结构；禁止使用历史名单或猜测解析规则。",
}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    entry = requests.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    entry.raise_for_status(); entry.encoding = "utf-8"
    soup = BeautifulSoup(entry.text, "html.parser")
    people: OrderedDict[str, list[str]] = OrderedDict()
    pattern = re.compile(r"[\u3400-\u9fff]{2,4}(?:（[^）]+）)?|[\u3400-\u9fff]\s+[\u3400-\u9fff](?:（[^）]+）)?")
    for link in soup.select(".submenu a[href]"):
        title = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        if "纪律检查委员会" not in title and "监察委员会" not in title:
            continue
        response = requests.get(urljoin(entry.url, str(link.get("href") or "")), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status(); response.encoding = "utf-8"
        section = "中国共产党青海省第十四届纪律检查委员会" if "纪律检查委员会" in title else "青海省监察委员会"
        for text in BeautifulSoup(response.text, "html.parser").stripped_strings:
            match = re.match(r"\s*(书\s*记|副书记|常\s*委|主\s*任|副主任)\s*[：:]\s*(.+)", text.replace("\xa0", " "))
            if match is None:
                continue
            role = re.sub(r"\s+", "", match.group(1)).replace("常委", "常务委员会委员")
            for raw_name in pattern.findall(match.group(2)):
                name = re.sub(r"[（(].*?[）)]|\s+", "", raw_name)
                duties = people.setdefault(name, []); duty = section + role
                if duty not in duties: duties.append(duty)
    rows = [{"name": n, "duty": "；".join(ds), "evidence": "；".join(ds), "detail_url": "", "parser": str(page_rule["parser"]), "selector_summary": "纪委监委双子页目标职务行"} for n, ds in people.items()]
    if not rows: raise RuntimeError("双子页未提取到目标领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
