from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urljoin
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
PAGE_RULE={"rule_id":"4099","page_type":"领导卡片页","structure_group":"sari_leader_h2_h3_card","reuse_scope":"page_structure","load_mode":"静态HTML直出","extract_mode":"list_direct","parser":"page_inline_sari_leader_h2_h3_card","leader_region_selector":".xrld-box .header-list","risk_flag":"新版现任领导卡片直接包含.title和.zw且无独立人物链接","confidence":"high","filter_policy":"strong_no_wordlist"}
def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析当前现任领导模块的姓名与职务卡片，排除导航及历任领导。"""
    import re
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".xrld-box .header-list"):
        if any(n.has_attr("hidden") or n.get("aria-hidden") == "true" or "display:none" in str(n.get("style", "")).replace(" ", "") for n in [card, *card.parents]):
            continue
        name_node, duty_node = card.select_one(".title"), card.select_one(".zw")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True)) if name_node else ""
        duty = " ".join(duty_node.get_text(" ", strip=True).split()) if duty_node else ""
        if re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) and duty:
            rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": ""})
    if not rows:
        raise RuntimeError("当前现任领导卡片未取得明确姓名职务")
    return rows


def main()->None:
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path=run_page_adapter(PAGE_RULE,globals());print(f"输出文件：{output_path}")
if __name__=='__main__':main()
