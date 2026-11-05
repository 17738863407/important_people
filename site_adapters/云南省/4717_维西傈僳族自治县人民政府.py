"""当前在线领导页面的专属技术解析规则。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

PAGE_RULE = {'rule_id': '4717', 'card_selector': '.leaderImg .leaderImgDl dd', 'name_selector': '.text .name', 'duty_selector': '.text .duty', 'detail_selector': 'a.con[href]', 'detail_pattern': '/ldyview/\\d+/\\d+\\.html$', 'verification_note': '仅政府领导信息leaderImgDl dd人物，text name姓名与duty完整职务，保留提名副县长限定及县人民政府党组成员兼办公室任职，排除其他部门导航，DOM顺序与独立ldyview人物页'}


def visible(node):
    """排除节点及祖先明确隐藏状态，保持DOM原顺序。"""
    for element in [node, *node.parents]:
        style = re.sub(r"\s+", "", str(element.get("style", ""))).lower()
        if element.has_attr("hidden") or element.get("aria-hidden") == "true" or "display:none" in style or "visibility:hidden" in style:
            return False
    return True


def parse_page(html, final_url, page_rule):
    if page_rule.get("unverified_reason"):
        raise RuntimeError(page_rule["unverified_reason"])
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(page_rule["card_selector"])
    if not cards:
        raise RuntimeError("当前页面未命中已核验人物卡片结构")
    records = []
    seen = set()
    for card in cards:
        if not visible(card):
            continue
        name_node = card.select_one(page_rule["name_selector"])
        duty_region = card.find_parent(page_rule["duty_ancestor"]) if page_rule.get("duty_ancestor") else card
        if page_rule.get("duty_ancestor_class"):
            duty_region = card.find_parent(class_=page_rule["duty_ancestor_class"])
        duty_node = duty_region.select_one(page_rule["duty_selector"]) if duty_region else None
        if name_node is None or duty_node is None:
            raise RuntimeError("人物卡片缺少已核验姓名或职务字段")
        name = re.sub(r"[\s\u200b-\u200d\ufeff]+", "", name_node.get_text(" ", strip=True))
        evidence = re.sub(r"\s+", " ", duty_node.get_text(" ", strip=True)).strip()
        raw_name, raw_duty = name, evidence
        if page_rule.get("combined_heading_pattern"):
            combined = re.fullmatch(page_rule["combined_heading_pattern"], name_node.get_text(" ", strip=True))
            if combined:
                heading_duty = combined.group(1)
                if duty_node is name_node or name_node in duty_node.parents:
                    evidence = heading_duty
                elif heading_duty not in evidence:
                    evidence = heading_duty if evidence in heading_duty else heading_duty + "；" + evidence
                name = re.sub(r"\s+", "", combined.group(2))
        if page_rule.get("name_suffix_pattern"):
            suffix = re.search(page_rule["name_suffix_pattern"], name)
            if suffix:
                name = name[:suffix.start()]
                evidence += suffix.group(0)
        if not re.fullmatch(r"[\u3400-\u9fff·•]{2,15}", name) or not evidence:
            raise RuntimeError("人物姓名或职务字段异常，需重新核验")
        if name in seen:
            raise RuntimeError("人物重复，需核验页面分组或响应结构")
        seen.add(name)
        link = card.select_one(page_rule.get("detail_selector", "a[href]"))
        href = str(link.get("href", "")) if link else ""
        detail_url = urljoin(final_url, href) if href and not href.startswith(("#", "javascript:", "mailto:")) else ""
        if detail_url == final_url or detail_url == page_rule["url"]:
            detail_url = ""
        if detail_url and not re.search(page_rule.get("detail_pattern", r"/info/\d+/\d+\.htm"), urlsplit(detail_url).path):
            detail_url = ""
        records.append({"name":name,"evidence":evidence,"detail_url":detail_url,
                        "source_name":raw_name,"source_duty":raw_duty})
    return records


def resolve_project_dir() -> Path:
    """从当前脚本向上寻找项目标记，兼容任意脚本层级。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
