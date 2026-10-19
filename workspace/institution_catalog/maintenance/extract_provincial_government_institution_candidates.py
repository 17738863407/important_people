"""从省级政府机构目录HTML中提取按机构类别分组的候选机构。"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

from crawler_core.paths import resolve_project_path


CATEGORY_TERMS = (
    "政府办公厅",
    "人民政府办公厅",
    "政府组成部门",
    "组成部门",
    "政府直属特设机构",
    "直属特设机构",
    "政府直属机构、直属事业单位",
    "直属机构、直属事业单位",
    "政府直属机构",
    "直属机构",
    "政府部门管理机构、事业单位",
    "部门管理机构、事业单位",
    "政府部门管理机构",
    "部门管理机构",
    "政府派出机构",
    "派出机构",
    "政府直属事业单位",
    "直属事业单位",
    "政府直属单位",
    "直属单位",
    "政府工作部门",
    "工作部门",
    "垂直管理机构",
    "其他机构",
)

STOP_TERMS = (
    "国务院部门",
    "各省（区市）政府",
    "各省区市政府",
    "市州（县市区）",
    "市州县区",
    "市县区政府",
    "中央驻",
    "中央在",
    "友情链接",
    "相关链接",
    "新闻媒体",
)

INSTITUTION_ENDINGS = (
    "厅",
    "局",
    "委",
    "委员会",
    "办公室",
    "办",
    "中心",
    "研究院",
    "研究所",
    "科学院",
    "社科院",
    "农科院",
    "学院",
    "大学",
    "馆",
    "总队",
    "总台",
    "联社",
    "联合社",
    "协会",
    "学会",
    "总会",
    "集团",
    "公司",
    "机构",
    "室",
    "署",
    "院",
    "社",
    "会",
    "联",
)


def configure_logging(log_path: Path) -> logging.Logger:
    """同时输出控制台日志和UTF-8文件日志。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("provincial_government_candidate_extractor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def normalize_text(value: str) -> str:
    """清理页面纯排版空白和项目符号。"""
    text = re.sub(r"[\u200b\ufeff\xa0\s]+", "", value)
    return text.strip("·•●▪◆◇►▶▷+＋|｜：:，,。;；")


def category_from_text(text: str) -> str:
    """识别短小、独立的政府机构分类标题。"""
    clean = normalize_text(text)
    if not clean or len(clean) > 32:
        return ""
    if any(term in clean for term in STOP_TERMS):
        return ""
    if any(word in clean for word in ("职责", "主要职责", "主办", "承办", "版权所有", "文件", "信息公开")):
        return ""
    for term in sorted(CATEGORY_TERMS, key=len, reverse=True):
        if clean.endswith(term):
            return clean
    return ""


def is_stop_text(text: str) -> bool:
    """判断页面是否已经进入非目标链接分区。"""
    clean = normalize_text(text)
    return 2 <= len(clean) <= 32 and any(term in clean for term in STOP_TERMS)


def has_child_category(node: Tag) -> bool:
    """排除仅因包含子节点文本而被误识别的外层容器。"""
    return any(category_from_text(child.get_text(" ", strip=True)) for child in node.find_all(True))


def is_footer_like(node: Tag) -> bool:
    """识别页脚、友情链接和底部导航容器。"""
    current: Tag | None = node
    while isinstance(current, Tag):
        identity = " ".join(
            [current.name, current.get("id", ""), *current.get("class", [])]
        ).lower()
        if re.search(r"(?:footer|foot|bottom|copyright|yqlj|friendlink|friend-link)", identity):
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def is_institution_name(text: str) -> bool:
    """使用机构名称后缀和导航黑名单筛选候选名称。"""
    clean = normalize_text(text)
    if not 2 <= len(clean) <= 50:
        return False
    if any(
        word in clean
        for word in (
            "首页",
            "政府信息公开",
            "政务公开",
            "政策",
            "新闻",
            "通知",
            "公告",
            "指南",
            "地图",
            "声明",
            "联系我们",
            "领导活动",
            "机构职能",
            "进入网站",
            "查看更多",
        )
    ):
        return False
    return clean.endswith(INSTITUTION_ENDINGS)


def resolve_href(base_url: str, href: str) -> str:
    """解析有效HTTP链接，无效占位链接按用户要求留空。"""
    clean = href.strip()
    if not clean or clean.startswith(("#", "javascript:", "mailto:")):
        return ""
    resolved = urljoin(base_url, clean)
    if urlparse(resolved).scheme.lower() not in {"http", "https"}:
        return ""
    return resolved


def leaf_category_nodes(body: Tag) -> list[tuple[Tag, str]]:
    """取得不会因包含子标题而重复的最深层分类标题节点。"""
    nodes: list[tuple[Tag, str]] = []
    for node in body.find_all(True):
        category = category_from_text(node.get_text(" ", strip=True))
        if category and not has_child_category(node):
            nodes.append((node, category))
    return nodes


def candidate_anchors(container: Tag) -> list[Tag]:
    """取得容器内名称形态符合机构的链接。"""
    return [
        anchor
        for anchor in container.find_all("a", href=True)
        if not is_footer_like(anchor)
        and is_institution_name(anchor.get_text(" ", strip=True))
        and not category_from_text(anchor.get_text(" ", strip=True))
    ]


def scoped_category_container(node: Tag, body: Tag) -> Tag | None:
    """向上寻找只包含当前一个分类标题且含机构链接的最小容器。"""
    current = node.parent
    while isinstance(current, Tag) and current is not body:
        categories = {
            category_from_text(descendant.get_text(" ", strip=True))
            for descendant in current.find_all(True)
            if category_from_text(descendant.get_text(" ", strip=True))
            and not has_child_category(descendant)
        }
        anchors = candidate_anchors(current)
        node_category = category_from_text(node.get_text(" ", strip=True))
        if anchors and len(categories) <= 1 and not ("办公厅" in node_category and len(anchors) > 2):
            return current
        if len(categories) > 1:
            return None
        current = current.parent
    return None


def extract_rows(region: str, base_url: str, html: str) -> list[list[str]]:
    """按照DOM顺序将机构链接归入最近的有效分类标题。"""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup
    rows: list[list[str]] = []
    seen_names: set[str] = set()
    categories = leaf_category_nodes(body)
    scoped_node_ids: set[int] = set()

    def add_row(category: str, name: str, href: str) -> None:
        clean_name = normalize_text(name)
        name_key = re.sub(r"[（）()、，,。·\s]+", "", clean_name)
        if not clean_name or name_key in seen_names:
            return
        resolved_href = resolve_href(base_url, href)
        rows.append([region, resolved_href, category, clean_name, resolved_href])
        seen_names.add(name_key)

    for node, category in categories:
        if "办公厅" in category:
            href = node.get("href", "") if node.name == "a" else ""
            add_row(category, category, href)
        container = scoped_category_container(node, body)
        if container is None:
            continue
        scoped_node_ids.add(id(node))
        for anchor in candidate_anchors(container):
            add_row(category, anchor.get_text(" ", strip=True), anchor.get("href", ""))

    current_category = ""

    for node in body.descendants:
        if not isinstance(node, Tag):
            continue
        if is_footer_like(node):
            current_category = ""
            continue
        text = normalize_text(node.get_text(" ", strip=True))

        if is_stop_text(text) and not node.find(True):
            current_category = ""
            continue

        category = category_from_text(text)
        if category and not has_child_category(node):
            current_category = category
            if id(node) in scoped_node_ids:
                current_category = ""
            continue

        if node.name != "a" or not current_category:
            continue
        name = normalize_text(node.get_text(" ", strip=True))
        if not is_institution_name(name) or category_from_text(name):
            continue
        add_row(current_category, name, node.get("href", ""))
    return rows


def write_rows(output_path: Path, rows: list[list[str]]) -> None:
    """写入用户要求的五列UTF-8制表符文本。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = ["区域", "目录链接", "机构大类名称", "机构小类名称", "机构链接"]
    with output_path.open("w", encoding="utf-8", newline="") as file:
        file.write("\t".join(header) + "\n")
        for row in rows:
            file.write("\t".join(cell.replace("\t", " ").replace("\r", " ").replace("\n", " ") for cell in row) + "\n")


def main(
    region_entries: list[tuple[int, str, str]],
    snapshot_dir: Path,
    output_path: Path,
    log_path: Path,
) -> None:
    """逐省读取快照、提取候选机构并汇总输出。"""
    logger = configure_logging(log_path)
    all_rows: list[list[str]] = []
    html_files = list(snapshot_dir.glob("*.html"))

    for index, region, base_url in tqdm(region_entries, desc="提取机构候选", unit="省级地区"):
        prefix = f"{index:02d}_"
        snapshot = next((path for path in html_files if path.name.startswith(prefix)), None)
        if snapshot is None:
            logger.error("缺少HTML快照：%02d %s", index, region)
            continue
        try:
            html = snapshot.read_text(encoding="utf-8")
            rows = extract_rows(region, base_url, html)
            all_rows.extend(rows)
            logger.info("提取：%02d %s，共%d项", index, region, len(rows))
        except Exception:
            logger.exception("提取失败：%02d %s", index, region)

    write_rows(output_path, all_rows)
    logger.info("候选提取结束：共%d项，输出：%s", len(all_rows), output_path)


if __name__ == "__main__":
    region_entries = [
        (1, "安徽省人民政府", "https://www.ah.gov.cn/site/tpl/2121"),
        (2, "北京市人民政府", "https://www.beijing.gov.cn/gongkai/zfxxgk/fdzdgknr/jgzn/"),
        (3, "重庆市人民政府", "https://www.cq.gov.cn/zwgk/zfxxgkzl/fdzdgknr/jgjj/jgzn/"),
        (4, "福建省人民政府", "https://www.fujian.gov.cn/szf/szfjg/"),
        (5, "甘肃省人民政府", "https://www.gansu.gov.cn/gsszf/c100084/xxgk_xgjj.shtml"),
        (6, "广东省人民政府", "https://www.gd.gov.cn/zwgk/szfjg/index.html"),
        (7, "广西壮族自治区人民政府", "http://www.gxzf.gov.cn/zwgk/zfxxgkzl_84988/gsqsbmptlj_85019/"),
        (8, "贵州省人民政府", "https://www.guizhou.gov.cn/zwgk/zfjg/"),
        (9, "海南省人民政府", "https://www.hainan.gov.cn/hainan/zfjg/zfjg.shtml?ddtab=true"),
        (10, "河北省人民政府", "https://www.hebei.gov.cn/columns/7e3d7892-9ecf-4a05-b5b1-90e772ff4509/index.html"),
        (11, "黑龙江省人民政府", "https://www.hlj.gov.cn/hlj/c108396/jgsz.shtml"),
        (12, "河南省人民政府", "https://www.henan.gov.cn/zwgk/zfjg/"),
        (13, "湖北省人民政府", "https://www.hubei.gov.cn/xxgk/zd/zfgzjg/"),
        (14, "湖南省人民政府", "https://www.hunan.gov.cn/hnszf/szf/zfjg/zzjg.html"),
        (15, "江苏省人民政府", "https://www.jiangsu.gov.cn/col/col84261/index.html"),
        (16, "江西省人民政府", "https://www.jiangxi.gov.cn/jxsrmzf/szfjg/pc/list.html#szfzc"),
        (17, "吉林省人民政府", "https://www.jl.gov.cn/szf/szfzzjg/"),
        (18, "辽宁省人民政府", "https://www.ln.gov.cn/web/zwgkx/zfjg_140150/index.shtml"),
        (19, "内蒙古自治区人民政府", "https://www.nmg.gov.cn/zwgk/zfjg2026/nmgzzqrmzfbgt/"),
        (20, "宁夏回族自治区人民政府", "https://www.nx.gov.cn/zwgk/zfxxgk/fdzdgknr/jgjj/"),
        (21, "青海省人民政府", "http://www.qinghai.gov.cn/xxgk/xxgk/fd/jg/jgzn/index.html"),
        (22, "山东省人民政府", "http://www.shandong.gov.cn/col/col305184/index.html?vc_xxgkarea=113700000045022274&number=SD26"),
        (23, "上海市人民政府", "https://www.shanghai.gov.cn/nw49254/index.html"),
        (24, "陕西省人民政府", "https://www.shaanxi.gov.cn/szf/jgzn01/"),
        (25, "山西省人民政府", "https://www.shanxi.gov.cn/zfxxgk/zfxxgkzl/fdzdgknr/jgjj/"),
        (26, "四川省人民政府", "https://www.sc.gov.cn/10462/ptlinks/szptlinks.shtml"),
        (27, "天津市人民政府", "https://www.tj.gov.cn/zwgk/szfjg/#t5"),
        (28, "新疆维吾尔自治区人民政府", "https://www.xinjiang.gov.cn/xinjiang/zfjg/zfjg.shtml"),
        (29, "西藏自治区人民政府", "https://www.xizang.gov.cn/zwgk/zfxxgk/fdzdgknr/jgjj/#xzzfjg"),
        (30, "云南省人民政府", "https://www.yn.gov.cn/szf/zfjg/"),
        (31, "浙江省人民政府", "https://www.zj.gov.cn/col/col1544854/index.html"),
    ]
    snapshot_dir = resolve_project_path(r"important_people/workspace/snapshots/机构目录/省级政府机构目录/html", anchor=__file__, must_exist=True)
    output_path = resolve_project_path(r"important_people/workspace/reports/机构目录/省级政府机构候选初稿.txt", anchor=__file__)
    log_path = resolve_project_path(r"important_people/workspace/log/机构目录/省级政府机构候选提取.log", anchor=__file__)
    main(region_entries, snapshot_dir, output_path, log_path)
