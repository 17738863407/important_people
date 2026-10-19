from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0799',
 'domain': 'www.gxzx.gov.cn',
 'page_type': '多人物详情合并页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_guangxi_zx_leader_dl_group_v1',
 'leader_region_selector': 'dl',
 'name_selector': '',
 'duty_selector': '',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': [], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': 'a[href]',
                     'detail_parser': 'V003_table_compound_person_v1',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50,
                     'candidate_links': []},
 'risk_flag': '原详情链误入新闻栏目并产生伪姓名；需限定政协领导dl姓名职位，并用页面分组补齐空职位',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 
 'locator_strategy': 'custom_parse_page',
 'locator': {'css': {'leader_region_selector': 'dl',
                     'name_selector': '',
                     'duty_selector': '',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': [],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '目录详情类页面使用列表页详情链接组件逐页解析'},
             'migration': {'source': 'sequential_detail_chain_builder',
                           'verified_status': 'pending',
                           'behavior_changed': True}}}


def clean_text(value: str) -> str:
    """压缩网页文本空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def duty_from_current_sentence(sentence: str) -> str:
    """从当前人物区域“现任”句判定政协职务。"""
    if re.search(r"(?:政协|人民政协)[^。]{0,20}秘书长", sentence):
        return "秘书长"
    if re.search(r"(?:政协|人民政协)副主席", sentence):
        return "副主席"
    if re.search(r"(?:政协|人民政协)主席", sentence):
        return "主席"
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析广西壮族自治区政协领导姓名与职务。"""
    soup = BeautifulSoup(html, "html.parser")
    source_url = str(page_rule.get("url", "")) or final_url
    rows: list[dict[str, str]] = []
    entries: list[dict[str, str]] = []
    nodes = soup.find_all("dl")
    pending_name = ""

    for index, node in enumerate(nodes):
        text = clean_text(node.get_text(" ", strip=True))
        if text.startswith("姓名："):
            pending_name = clean_text(text.split("：", 1)[1]).replace(" ", "")
            continue
        if not pending_name or not text.startswith("职位："):
            continue
        raw_duty = clean_text(text.split("：", 1)[1])
        current_sentence = ""
        for following in nodes[index + 1:]:
            following_text = clean_text(following.get_text(" ", strip=True))
            if following_text.startswith("姓名："):
                break
            match = re.search(r"现任[^。]*(?:。|$)", following_text)
            if match:
                current_sentence = match.group(0)
                break
        duty = raw_duty or duty_from_current_sentence(current_sentence)
        name = pending_name
        pending_name = ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        evidence = raw_duty or (
            re.sub(r"^现任\s*", "", current_sentence).rstrip("。")
            if current_sentence.endswith("。")
            else duty
        )
        entries.append({"name": name, "duty": duty, "evidence": evidence})

    chair_index = next((index for index, entry in enumerate(entries) if entry["duty"] == "主席"), -1)
    secretary_index = next(
        (index for index, entry in enumerate(entries) if entry["duty"] == "秘书长"),
        len(entries),
    )
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        name = entry["name"]
        duty = entry["duty"]
        if not duty and chair_index < index < secretary_index:
            duty = "副主席"
        if not duty or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": entry["evidence"] or duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "政协领导dl姓名/职位字段；空职位按页面主席、副主席、秘书长分组补齐",
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
