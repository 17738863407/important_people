from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '2281',
 'domain': 'www.scspc.gov.cn',
 'page_type': '图片名单型',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'static_http',
 'parser': 'custom_scspc_rdgk_cwhld_v1',
 'leader_region_selector': '#cwhld .cwhld-leader-name, #cwhld .cwhld-name',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"image_asset","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '领导信息存储在图片中；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '#cwhld .cwhld-leader-name, #cwhld .cwhld-name',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面直接使用 CSS/HTML 定位解析'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'generated',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def clean_name(text: str) -> str:
    return "".join(clean_text(text).split())


def normalize_detail_url(href: str, base_url: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    return urljoin(base_url, href)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    root = soup.select_one("#cwhld") or soup
    rows: list[dict] = []
    seen: set[str] = set()

    for box in root.select(".cwhld-leader-name, .cwhld-name"):
        paragraphs = [clean_text(p.get_text(" ", strip=True)) for p in box.find_all("p")]
        paragraphs = [item for item in paragraphs if item]
        if len(paragraphs) < 2:
            continue
        duty = paragraphs[0]
        name = clean_name(paragraphs[1])
        if not name or name in seen:
            continue
        if not any(keyword in duty for keyword in ("主任", "副主任", "秘书长")):
            continue
        link = box.find("a", href=True)
        entry_url = final_url or page_rule["url"]
        detail_url = normalize_detail_url(link["href"], entry_url) if link else ""
        if detail_url.rstrip("/") == entry_url.rstrip("/"):
            detail_url = ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "selector_summary": "#cwhld领导姓名职务p标签",
            }
        )

    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
