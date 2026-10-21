from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {"rule_id":"4021","page_type":"可视化建站领导区块","structure_group":"cits_absolute_leaders","reuse_scope":"single_page","load_mode":"静态HTML直出","fetch_mode":"raw_http","extract_mode":"custom","collector":"raw_http","parser":"custom_cits_absolute_leaders_v1","inline_parser_handles_fetch":True,"inline_fetch_collector":"raw_http","leader_region_selector":".editableContent（学会领导至联系我们）","name_selector":"姓名文本组件","duty_selector":"同区块职务标题及垂直位置","detail_link_selector":"姓名组件内a[href]","content_scope":{"start_anchor":"学会领导","end_anchor":"联系我们","include_selectors":[".editableContent"],"exclude_selectors":[]},"detail_strategy":{"required":False,"mode":"dynamic_link"},"risk_flag":"页面使用绝对定位，副会长和副会长兼秘书长依垂直坐标分组。","confidence":"medium","profile_reusable":False,"profile_judgement":"已核验实时HTML保留人物组件、职务标题和定位样式。","filter_policy":"strong_no_wordlist","locator_strategy":"custom_parse_page","locator":{"css":{"leader_region_selector":".editableContent"},"api":{"enabled":False,"reason":"HTML含完整领导组件"},"migration":{"verified_status":"verified"}}}


def position(node: object) -> tuple[int, int]:
    holder = node.find_parent("div", class_="smartAbs")
    style = holder.get("style", "") if holder else ""
    top = re.search(r"top:\s*(\d+)px", style)
    left = re.search(r"left:\s*(\d+)px", style)
    return (int(top.group(1)) if top else -1, int(left.group(1)) if left else -1)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    session = requests.Session()
    session.trust_env = False
    response = session.get(str(page_rule["url"]), timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    html, final_url = response.content.decode("utf-8", errors="replace"), response.url
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(".editableContent")
    start = next((index for index, block in enumerate(blocks) if block.get_text(" ", strip=True) == "学会领导"), -1)
    end = next((index for index in range(start + 1, len(blocks)) if blocks[index].get_text(" ", strip=True) == "联系我们"), len(blocks))
    leader_blocks = blocks[start + 1:end] if start >= 0 else []
    titles = {block.get_text(" ", strip=True): position(block)[0] for block in leader_blocks if block.get_text(" ", strip=True) in {"副会长", "副会长兼秘书长"}}
    rows: list[dict[str, str]] = []
    for block in leader_blocks:
        text = re.sub(r"[\s\u00a0\u200b]+", "", block.get_text(" ", strip=True))
        direct = re.fullmatch(r"会长([\u4e00-\u9fff]{2,4})", text)
        name = direct.group(1) if direct else text
        if direct:
            duty = "会长"
        elif name in {"副会长", "副会长兼秘书长"} or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name):
            continue
        else:
            top, _ = position(block)
            duty = "副会长兼秘书长" if top > titles.get("副会长兼秘书长", 10**9) else "副会长"
        link = block.select_one("a[href]")
        detail_url = urljoin(final_url, link["href"]) if link else ""
        rows.append({"name":name,"duty":duty,"detail_url":detail_url,"evidence":duty,"parser":str(page_rule["parser"]),"selector_summary":"学会领导区块内绝对定位姓名组件"})
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
