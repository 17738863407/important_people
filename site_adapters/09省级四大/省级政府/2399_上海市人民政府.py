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

PAGE_RULE = {'rule_id': '2399',
 'domain': 'www.shanghai.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'custom',
 'collector': 'online_html',
 'parser': 'custom_shanghai_gov_leader_cards_v1',
 'leader_region_selector': '.government-leaders .Government-list a[href], .government-left-right p',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'raw': '{"required":false,"mode":"none","detail_collector_type":"image_asset","detail_link_selector":null,"detail_name_selector":"","detail_duty_selector":"","detail_content_selector":"","max_detail_links":50,"candidate_links":[]}'},
 'risk_flag': '市长、副市长和党组成员为人物链接；秘书长分组无人物详情链接',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'weak_allow_wordlist',
 
 'locator_strategy': 'css',
 'locator': {'css': {'leader_region_selector': '.government-leaders .Government-list a[href], '
                                               '.government-left-right p',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线页面使用 CSS/HTML 定位解析'},
             'migration': {'source': 'last_batch_online_template',
                           'verified_status': 'generated',
                           'behavior_changed': True}}}


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def split_role_name(text: str) -> tuple[str, str]:
    value = clean_text(text)
    if "：" not in value:
        return "", ""
    duty, name = value.split("：", 1)
    return clean_text(duty), "".join(clean_text(name).split())


def resolve_detail_url(base_url: str, source_url: str, href: str) -> str:
    """仅保留与领导入口页不同的真实人物链接。"""
    value = str(href or "").strip()
    if not value or value.startswith(("#", "javascript:")):
        return ""
    detail_url = urljoin(base_url, value)
    return "" if detail_url.rstrip("/") == source_url.rstrip("/") else detail_url


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()

    for node in soup.select(".government-leaders .Government-list a[href]"):
        text = clean_text(node.get_text(" ", strip=True))
        duty, name = split_role_name(text)
        if not duty or not name or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": resolve_detail_url(final_url or page_rule["url"], page_rule["url"], node.get("href") or ""),
                "evidence": duty,
                "selector_summary": "市政府领导图片链接p文本",
            }
        )

    for secretary in soup.select(".government-left-right p"):
        label_node = secretary.select_one("label")
        label = clean_text(label_node.get_text(" ", strip=True) if label_node else "").rstrip("：:")
        for name_node in secretary.select("small"):
            name = "".join(clean_text(name_node.get_text(" ", strip=True)).split())
            if label and name and name not in seen:
                seen.add(name)
                rows.append(
                    {
                        "name": name,
                        "duty": label,
                        "detail_url": "",
                        "evidence": label,
                        "selector_summary": f"{label}可见文本",
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
