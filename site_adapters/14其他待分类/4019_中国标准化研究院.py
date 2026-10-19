from __future__ import annotations
import re, sys
from pathlib import Path
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id":"4019","page_type":"移动端领导名单页","structure_group":"cnis_wap_leaders","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cnis_wap_leaders_v1","leader_region_selector":".m_floor_itt .xgzf","name_selector":"li > a 的姓名前缀","duty_selector":"li > a 的姓名后文本","detail_link_selector":"","content_scope":{"start_anchor":"现任领导","end_anchor":"地址：","include_selectors":[".m_floor_itt .xgzf"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"姓名和职务在同一文本节点，以全角空格分隔。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验当前入口的现任领导列表为独立静态列表。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".m_floor_itt .xgzf"},"api":{"enabled":False,"reason":"HTML含完整名单"},"migration":{"verified_status":"verified"}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    root = BeautifulSoup(html, "html.parser").select_one(".m_floor_itt .xgzf")
    rows: list[dict[str, str]] = []
    for item in root.select(":scope > li") if root else []:
        parts = [part for part in re.split(r"[\s\u3000]+", item.get_text(" ", strip=True)) if part]
        if len(parts) < 2:
            continue
        if len(parts[0]) == 1 and len(parts) >= 3:
            name, duty = parts[0] + parts[1], "".join(parts[2:])
        else:
            name, duty = parts[0], "".join(parts[1:])
        if duty:
            rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":".m_floor_itt .xgzf > li"})
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
