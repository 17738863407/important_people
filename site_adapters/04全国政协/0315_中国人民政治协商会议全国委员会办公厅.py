from __future__ import annotations

import sys
from pathlib import Path
def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")



def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析全国政协办公厅领导区块，避免把工作动态新闻解析成人物。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    block = soup.select_one(".zhengxie17370_shipinji_ind03_1214")
    if block is None:
        return []

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.zhengxie17370_shipinji_ind03_1214；"
        "name=.zhuren .name a,.renyuan .fzr li；duty=.title；detail=秘书长链接；api_enabled=False"
    )

    def normalize_person_text(text: str) -> tuple[str, str]:
        cleaned = re.sub(r"\s+", "", text).strip()
        note_match = re.search(r"（(?P<note>[^）]+)）", cleaned)
        note = note_match.group("note").strip() if note_match else ""
        name = re.sub(r"（[^）]+）", "", cleaned).replace("\u3000", "").strip()
        return name, note

    def add_row(raw_name: str, base_duty: str, detail_url: str = "") -> None:
        name, note = normalize_person_text(raw_name)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            return
        duty = base_duty
        if "兼职" in note:
            duty = f"{base_duty}（兼职）"
        key = (name, duty)
        if key in seen:
            return
        seen.add(key)
        evidence = duty
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")),
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": "page_inline_cppcc_office_leaders_v1",
                "selector_summary": selector_summary,
            }
        )

    secretary = block.select_one(".zhuren .name a, .zhuren .name")
    if secretary is not None:
        secretary_link = secretary if secretary.name == "a" else secretary.select_one("a[href]")
        href = str(secretary_link.get("href", "")).strip() if secretary_link is not None else ""
        add_row(secretary.get_text(" ", strip=True), "秘书长", urljoin(final_url, href) if href else "")

    deputy_container = None
    for container in block.select(".renyuan"):
        title = container.select_one(".title")
        if title and "副秘书长" in title.get_text(" ", strip=True):
            deputy_container = container
            break
    if deputy_container is not None:
        for node in deputy_container.select(".fzr li"):
            add_row(node.get_text(" ", strip=True), "副秘书长")

    return rows


PAGE_RULE = {'rule_id': '0315',
 'domain': 'www.cppcc.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': 'cppcc_role_group',
 'reuse_scope': 'page_structure',
 'load_mode': '接口数据加载',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'browser_dom',
 'parser': 'page_inline_cppcc_office_leaders_v1',
 'leader_region_selector': '.zhengxie17370_shipinji_ind03_1214',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'candidate_links': []},
 'risk_flag': '新闻人物或正文干扰；第二轮定向修复',
 'confidence': 'low',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': '.zhengxie17370_shipinji_ind03_1214',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '当前脚本缺少可复现 api 配置；本次迁移保留旧定位字段，后续逐页接口探测', 'probe_status': '需要逐页探测'},
             'migration': {'source': 'legacy_page_rule', 'verified_status': 'success_dir', 'behavior_changed': True}}}


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



