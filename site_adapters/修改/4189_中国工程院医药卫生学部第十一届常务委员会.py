from __future__ import annotations
import re,sys
from pathlib import Path
def resolve_project_dir()->Path:
 for p in Path(__file__).resolve().parents:
  if (p/'crawler_core').is_dir():return p
 raise RuntimeError('未找到包含 crawler_core 的项目根目录')
PAGE_RULE={'rule_id':'4189','page_type':'学部常委会公示页','load_mode':'静态HTML直出','extract_mode':'list_direct','parser':'page_inline_cae_committee_v1','leader_region_selector':'#zoom','name_selector':'','duty_selector':'','detail_link_selector':'','detail_strategy':{'required':False,'mode':'none'},'confidence':'high','filter_policy':'strong_no_wordlist'}
def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按目标学部标题边界完整读取主任、副主任及跨段委员名单。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#zoom")
    if region is None:
        raise RuntimeError("未找到学部常委会正文#zoom")
    title = re.sub(r"\s+", "", str(page_rule["organization"]).removeprefix("中国工程院"))
    inside = False
    active_role = ""
    records: dict[str, dict] = {}
    for paragraph in region.find_all("p", recursive=False):
        if any(n.has_attr("hidden") or n.get("aria-hidden") == "true" or "display:none" in str(n.get("style", "")).replace(" ", "") for n in [paragraph, *paragraph.parents]):
            continue
        text = re.sub(r"\s+", "", paragraph.get_text(" ", strip=True))
        if text.endswith("常务委员会"):
            if inside:
                break
            inside = text == title
            continue
        if not inside or not text:
            continue
        match = re.match(r"^(主任|副主任|委员)[：:](.*)$", text)
        if match:
            active_role, names_text = match.groups()
        elif active_role:
            names_text = text
        else:
            continue
        names_text = re.sub(r"[（(][^）)]*[）)]", "", names_text)
        for name in re.split(r"[、，,]", names_text):
            if not name:
                continue
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,8}", name):
                raise RuntimeError("目标常委会出现不能确认的姓名字段")
            if name not in records:
                records[name] = {"name": name, "duty": active_role, "evidence": active_role, "detail_url": ""}
            elif active_role not in records[name]["evidence"].split("；"):
                records[name]["evidence"] += "；" + active_role
                records[name]["duty"] = records[name]["evidence"]
    if not inside or not records:
        raise RuntimeError("未取得目标学部常委会完整名单")
    return list(records.values())


def main()->None:
 d=resolve_project_dir();sys.path.insert(0,str(d)) if str(d) not in sys.path else None
 from crawler_core.runner import run_page_adapter
 print(f'输出文件：{run_page_adapter(PAGE_RULE,globals())}')
if __name__=='__main__':main()
