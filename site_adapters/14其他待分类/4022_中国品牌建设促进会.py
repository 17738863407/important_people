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


PAGE_RULE = {"rule_id":"4022","page_type":"领导介绍正文页","structure_group":"ccbd_title_name_blocks","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_ccbd_title_name_blocks_v1","leader_region_selector":".content_main_con","name_selector":"职务标题后直接文本","duty_selector":"strong职务标题","detail_link_selector":"","content_scope":{"start_anchor":"第三届理事会","end_anchor":"促进会介绍","include_selectors":[".content_main_con"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"none"},"risk_flag":"副理事长为顿号分隔名单，页面明确为同一职务。","confidence":"high","profile_reusable":False,"profile_judgement":"已核验实时正文使用稳定的强标签“职务：”及相邻名单。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".content_main_con"},"api":{"enabled":False,"reason":"HTML正文完整"},"migration":{"verified_status":"verified"}}}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    root = BeautifulSoup(html, "html.parser").select_one(".content_main_con")
    rows: list[dict[str, str]] = []
    for block in root.find_all("div", recursive=False) if root else []:
        label = block.find("strong")
        duty = re.sub(r"[：:\s]", "", label.get_text(" ", strip=True)) if label else ""
        if not duty:
            continue
        text = re.sub(r"\s+", "", block.get_text(" ", strip=True))
        names_text = text[len(label.get_text(" ", strip=True)):].strip(" ：:")
        for name in re.split(r"[、，,]\s*", names_text):
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
                rows.append({"name":name,"duty":duty,"detail_url":"","evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":".content_main_con > div > strong"})
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
