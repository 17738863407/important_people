"""读取领导卡片的姓名与职务分隔字段，限定县政府领导。"""
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "4693",
    "verification_note": "ml-ld-grid figure卡片的figcaption以全角冒号分隔姓名职务，职务后缀限定县长及副县长目标分组，排除办公室负责人，保持DOM顺序，独立ldjj人物页",
}


def parse_page(html, final_url, page_rule):
    soup = BeautifulSoup(html, "lxml")
    records = []
    for card in soup.select(".ml-ld-grid figure.ml-ld-card"):
        if any(node.has_attr("hidden") or node.get("aria-hidden") == "true" or "display:none" in re.sub(r"\s+", "", node.get("style", "")) for node in [card,*card.parents]):
            continue
        caption = card.select_one("figcaption.ml-ld-name")
        link = card.select_one("a.ml-ld-link[href]")
        if caption is None or link is None:
            raise RuntimeError("人物卡片缺少标题或独立链接")
        raw = caption.get_text(" ", strip=True)
        fields = re.fullmatch(r"([\u3400-\u9fff·]{2,15})\s*：\s*(.+)", raw)
        if not fields:
            raise RuntimeError("卡片姓名职务分隔结构变化")
        name, duty = fields.groups()
        if not re.search(r"人民政府(?:常务)?副?县长$", duty):
            continue
        detail_url = urljoin(final_url, link["href"])
        if not re.fullmatch(r"/zhengfuxinxigongkai/ldjj/\d+\.html", urlsplit(detail_url).path):
            raise RuntimeError("人物链接路径结构变化")
        records.append({"name":name,"evidence":duty,"detail_url":detail_url,
                        "source_name":raw,"source_duty":raw})
    return records


def resolve_project_dir() -> Path:
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
