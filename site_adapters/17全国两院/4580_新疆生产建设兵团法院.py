from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4580",
    "page_type": "首页领导图片轮播卡片",
    "structure_group": "bingtuan_court_home_leader_cards_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_inline_bingtuan_court_home_leader_cards_v2",
    "detail_strategy": {"required": False, "mode": "paired_image_and_name_anchor"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "限定首页领导成员及分工版块；按原始图片卡片出现顺序提取，排除装饰图和轮播克隆；职务只取同一卡片明确职务字段，简介和分工不混入。",
}


def is_hidden(node: Tag) -> bool:
    """排除节点或其祖先上明确隐藏的模板内容。"""
    for current in (node, *node.parents):
        if not isinstance(current, Tag):
            continue
        style = re.sub(r"\s+", "", str(current.get("style", "")).lower())
        classes = {str(item).lower() for item in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style or classes & {"hidden", "hide", "d-none", "slick-cloned"}:
            return True
    return False


def visible_text(node: Tag) -> str:
    """读取当前字段的可见文本，避免字段内部隐藏模板参与证据。"""
    return "".join(str(text) for text in node.find_all(string=True) if not is_hidden(text.parent))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """以首页人物头像卡片为锚点，按图片出现顺序读取姓名和职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    regions = [node for node in soup.select(".leader > .tabCon-leader > .swiper-leader") if not is_hidden(node)]
    if len(regions) != 1:
        raise ValueError("没有唯一可见的首页领导图片轮播区域")
    section = regions[0].find_parent(class_="catalog-item")
    headings = section.select(":scope > .catalogTit a") if section else []
    if not any(node.get_text(strip=True) == "领导成员及分工" for node in headings):
        raise ValueError("首页图片轮播不属于领导成员及分工版块")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in regions[0].select(":scope > .leader-item"):
        if is_hidden(card):
            continue
        # dt直属图片为装饰框，只有人物链接内的图片才作为头像顺序锚点。
        portraits = [node for node in card.select(":scope > dl > dt > a[href] > img[src]") if not is_hidden(node)]
        name_node = card.select_one(":scope > dl > dd.leadTit > a[href]")
        duty_nodes = [node for node in card.select(":scope > dl > dd")
                      if not is_hidden(node) and re.match(r"^\s*职务\s*[：:]", visible_text(node))]
        if len(portraits) != 1 or name_node is None or is_hidden(name_node) or len(duty_nodes) != 1:
            raise ValueError("人物卡片缺少唯一头像、姓名或职务字段")
        name = re.sub(r"\s+", "", visible_text(name_node))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            raise ValueError("首页人物卡片包含异常或重复姓名")
        seen.add(name)
        raw_duty = visible_text(duty_nodes[0])
        duty = re.sub(r"\s+", " ", re.sub(r"^\s*职务\s*[：:]\s*", "", raw_duty)).strip()
        if not duty:
            raise ValueError(f"首页卡片职务为空：{name}")
        detail_url = urljoin(final_url, str(name_node["href"]).strip())
        portrait_link = urljoin(final_url, str(portraits[0].parent["href"]).strip())
        parsed = urlsplit(detail_url)
        if (detail_url != portrait_link or parsed.scheme not in {"http", "https"} or parsed.netloc != urlsplit(final_url).netloc
                or re.fullmatch(r"/c/\d{4}-\d{2}-\d{2}/\d+\.shtml", parsed.path) is None):
            raise ValueError(f"头像和姓名没有指向同一独立人物页：{name}")
        rows.append({
            "name": name,
            "duty": duty,
            "evidence": duty,
            "detail_url": detail_url,
            "source_text": raw_duty,
            "method": str(page_rule["parser"]),
        })
        logging.info("首页图片卡片解析通过：%s，原始顺序%s", name, len(rows))
    if not rows:
        raise ValueError("首页领导图片轮播没有有效人物")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.paths import resolve_project_path
    from crawler_core.runner import run_page_adapter

    log_dir = resolve_project_path("workspace/log", anchor=__file__)
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_dir / f"{Path(__file__).stem}.log", encoding="utf-8")],
    )
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
