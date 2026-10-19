"""汇总31个省级政府机构目录，并与规则主表核对缺失机构。"""

from __future__ import annotations

import csv
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from tqdm import tqdm

from crawler_core.paths import resolve_project_path


def configure_logging(log_path: Path) -> logging.Logger:
    """同时配置控制台和UTF-8日志文件。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("provincial_government_inventory_builder")
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


def read_tsv(path: Path) -> list[dict[str, str]]:
    """读取UTF-8制表符文本。"""
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file, delimiter="\t"))


def write_inventory(path: Path, rows: list[dict[str, str]]) -> None:
    """按用户指定的五列写入UTF-8制表符文本。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["区域", "目录链接", "机构大类名称", "机构小类名称", "机构链接"]
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write("\t".join(fields) + "\n")
        for row in rows:
            values = [row.get(field, "").replace("\t", " ").replace("\r", " ").replace("\n", " ") for field in fields]
            file.write("\t".join(values) + "\n")


def write_audit(path: Path, rows: list[dict[str, str]]) -> None:
    """写入包含匹配依据的审计报告。"""
    fields = ["区域", "机构大类名称", "机构小类名称", "机构链接", "匹配状态", "匹配方式", "规则主表机构", "脚本序号", "官网链接", "领导链接", "相似度"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write("\t".join(fields) + "\n")
        for row in rows:
            file.write("\t".join(row.get(field, "").replace("\t", " ").replace("\r", " ").replace("\n", " ") for field in fields) + "\n")


def new_row(region: str, category: str, name: str, link: str = "") -> dict[str, str]:
    """创建统一的五列机构记录。"""
    clean_link = link.strip()
    return {
        "区域": region.strip(),
        "目录链接": "",
        "机构大类名称": category.strip(),
        "机构小类名称": name.strip(),
        "机构链接": clean_link,
    }


def parse_manual_inventory(region: str, text: str) -> list[dict[str, str]]:
    """解析因站点防护而依据官方清单补录的“分类|机构”文本。"""
    rows: list[dict[str, str]] = []
    category = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("【") and line.endswith("】"):
            category = line[1:-1].strip()
            continue
        if not category:
            raise ValueError(f"补录机构缺少分类：{region} {line}")
        rows.append(new_row(region, category, line))
    return rows


def parse_shanxi(html_path: Path, base_url: str) -> list[dict[str, str]]:
    """按山西页面的选项卡标题与内容面板一一对应提取。"""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    wrapper = soup.select_one("div.gov-members")
    if wrapper is None:
        raise ValueError("山西目录未找到gov-members容器")
    title_list = wrapper.select_one("ul.gov-members-title")
    if title_list is None:
        raise ValueError("山西目录未找到分类标题")
    categories = [item.get_text(" ", strip=True) for item in title_list.find_all("li", recursive=False)]
    panels = wrapper.find_all("div", class_="gov-members-box", recursive=False)
    if len(categories) != len(panels):
        raise ValueError(f"山西分类与面板数量不一致：{len(categories)} != {len(panels)}")
    rows: list[dict[str, str]] = []
    for category, panel in zip(categories, panels, strict=True):
        for anchor in panel.find_all("a", href=True):
            name = re.sub(r"职责$", "", anchor.get_text(" ", strip=True)).strip()
            if name:
                rows.append(new_row("山西省人民政府", category, name, urljoin(base_url, anchor["href"])))
    return rows


def anchors_between(html_path: Path, start_text: str, end_text: str) -> list[tuple[str, str]]:
    """从扁平部门链接页按首尾机构名称截取目标链接段。"""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    anchors = [(anchor.get_text(" ", strip=True), anchor.get("href", "")) for anchor in soup.find_all("a")]
    start_index = next(index for index, item in enumerate(anchors) if item[0] == start_text)
    end_index = next(index for index, item in enumerate(anchors[start_index:], start=start_index) if item[0] == end_text)
    return anchors[start_index : end_index + 1]


def parse_shanghai(html_path: Path, base_url: str) -> list[dict[str, str]]:
    """从上海书签页的市级部门平台链接段提取机构。"""
    rows = [new_row("上海市人民政府", "市政府办公厅", "上海市人民政府办公厅", "https://www.shanghai.gov.cn/nw2405/index.html")]
    for name, href in anchors_between(html_path, "市发展改革委", "市知识产权局"):
        rows.append(new_row("上海市人民政府", "市级部门政府信息公开平台", name, urljoin(base_url, href)))
    return rows


def parse_sichuan(html_path: Path, base_url: str) -> list[dict[str, str]]:
    """从四川书签页的省级部门平台链接段提取机构。"""
    rows = [new_row("四川省人民政府", "省政府办公厅", "四川省人民政府办公厅", "https://www.sc.gov.cn/10462/c102917/zfxxgk_jgjj.shtml")]
    for name, href in anchors_between(html_path, "省发展改革委", "省药监局"):
        rows.append(new_row("四川省人民政府", "省级部门政府信息公开平台", name, urljoin(base_url, href)))
    return rows


def clean_standard_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """去除通用解析误带的内设机构、页脚重复项并修正已核验分类。"""
    output: list[dict[str, str]] = []
    for row in rows:
        region = row["区域"]
        category = row["机构大类名称"]
        name = row["机构小类名称"]

        if region == "海南省人民政府" and name == "海南省政府机构":
            continue
        if region == "内蒙古自治区人民政府" and category == "自治区人民政府办公厅" and name != "自治区人民政府办公厅":
            continue
        if region == "江苏省人民政府":
            category = "省政府办公厅" if name == "省政府办公厅" else "省级部门政府信息公开平台"
        if region == "宁夏回族自治区人民政府" and category == "自治区政府直属特设机构" and "国有资产监督管理委员会" not in name:
            category = "自治区政府直属机构、直属事业单位"

        row = dict(row)
        row["机构大类名称"] = category
        output.append(row)
    return output


def supplement_yunnan_current_directory(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """补入云南目录当前末项，并严格保持其位于省文史馆之后。"""
    output: list[dict[str, str]] = []
    inserted = False
    for row in rows:
        output.append(row)
        if row["区域"] == "云南省人民政府" and row["机构小类名称"] == "省文史馆":
            output.append(
                new_row(
                    "云南省人民政府",
                    "云南省人民政府直属事业单位",
                    "云南广播电视台",
                    "https://ymg.yntv.cn/",
                )
            )
            inserted = True
    if not inserted:
        raise ValueError("云南目录未找到省文史馆，无法按网页顺序插入云南广播电视台")
    return output


def canonical_name(name: str, region: str) -> str:
    """将全称与常见目录简称转换为保守的比较键。"""
    text = re.split(r"[、，,]", name, maxsplit=1)[0]
    text = re.sub(r"[\s\u200b\ufeff·•。:：;；\-—_/]+", "", text)
    text = re.sub(r"[（(][^（）()]*[）)]", "", text)
    region_tokens = {
        "安徽省人民政府": ["安徽省", "安徽"], "北京市人民政府": ["北京市", "北京"],
        "重庆市人民政府": ["重庆市", "重庆"], "福建省人民政府": ["福建省", "福建"],
        "甘肃省人民政府": ["甘肃省", "甘肃"], "广东省人民政府": ["广东省", "广东"],
        "广西壮族自治区人民政府": ["广西壮族自治区", "广西自治区", "广西"],
        "贵州省人民政府": ["贵州省", "贵州"], "海南省人民政府": ["海南省", "海南"],
        "河北省人民政府": ["河北省", "河北"], "黑龙江省人民政府": ["黑龙江省", "黑龙江"],
        "河南省人民政府": ["河南省", "河南"], "湖北省人民政府": ["湖北省", "湖北"],
        "湖南省人民政府": ["湖南省", "湖南"], "江苏省人民政府": ["江苏省", "江苏"],
        "江西省人民政府": ["江西省", "江西"], "吉林省人民政府": ["吉林省", "吉林"],
        "辽宁省人民政府": ["辽宁省", "辽宁"],
        "内蒙古自治区人民政府": ["内蒙古自治区", "内蒙古"],
        "宁夏回族自治区人民政府": ["宁夏回族自治区", "宁夏自治区", "宁夏"],
        "青海省人民政府": ["青海省", "青海"], "山东省人民政府": ["山东省", "山东"],
        "上海市人民政府": ["上海市", "上海"], "陕西省人民政府": ["陕西省", "陕西"],
        "山西省人民政府": ["山西省", "山西"], "四川省人民政府": ["四川省", "四川"],
        "天津市人民政府": ["天津市", "天津"],
        "新疆维吾尔自治区人民政府": ["新疆维吾尔自治区", "新疆自治区", "新疆"],
        "西藏自治区人民政府": ["西藏自治区", "西藏"],
        "云南省人民政府": ["云南省", "云南"], "浙江省人民政府": ["浙江省", "浙江"],
    }
    for token in sorted(region_tokens.get(region, []), key=len, reverse=True):
        if text.startswith(token):
            text = text[len(token) :]
            break
    text = re.sub(r"^(?:省|市|自治区|区)", "", text)
    text = text.replace("人民政府", "政府")
    replacements = {
        "发展改革委": "发展和改革委员会", "发改委": "发展和改革委员会",
        "教委": "教育委员会", "科委": "科学技术委员会", "科技厅": "科学技术厅",
        "工信厅": "工业和信息化厅", "经济信息委": "经济和信息化委员会",
        "经济信息化委": "经济和信息化委员会", "商务委": "商务委员会",
        "民宗委": "民族宗教事务委员会", "民族宗教委": "民族宗教事务委员会",
        "民族宗教局": "民族和宗教事务局",
        "民委": "民族事务委员会",
        "人社厅": "人力资源和社会保障厅", "人力社保局": "人力资源和社会保障局",
        "规划自然资源局": "规划和自然资源局", "住建厅": "住房和城乡建设厅",
        "规划资源局": "规划和自然资源局",
        "规划自然资源委": "规划和自然资源委员会", "住房城乡建设委": "住房和城乡建设委员会",
        "住房城乡建设管理委": "住房和城乡建设管理委员会",
        "城市管理委": "城市管理委员会", "交通委": "交通委员会",
        "住房城乡建设厅": "住房和城乡建设厅", "文旅厅": "文化和旅游厅",
        "农业农村委": "农业农村委员会",
        "卫健委": "卫生健康委员会", "卫生健康委": "卫生健康委员会",
        "退役军人厅": "退役军人事务厅", "应急厅": "应急管理厅",
        "退役军人局": "退役军人事务局",
        "应急局": "应急管理局",
        "外办": "外事办公室", "国资委": "国有资产监督管理委员会",
        "市场监管局": "市场监督管理局", "广电局": "广播电视局",
        "医保局": "医疗保障局", "国动办": "国防动员办公室",
        "国防动员办": "国防动员办公室", "信访办": "信访办公室",
        "机管局": "机关事务管理局", "机关事务局": "机关事务管理局",
        "管局": "机关事务管理局",
        "粮食和储备局": "粮食和物资储备局", "粮食物资储备局": "粮食和物资储备局",
        "药监局": "药品监督管理局", "药品监管局": "药品监督管理局",
        "疾控局": "疾病预防控制局",
        "中医药局": "中医药管理局", "林草局": "林业和草原局",
        "政务和数据局": "政务服务和数据管理局",
        "地方金融监管局": "地方金融监督管理局",
        "绿化市容局": "绿化和市容管理局", "民防办": "国防动员办公室",
        "政府合作交流办": "政府合作交流办公室",
        "城管执法局": "城市管理行政执法局", "监狱局": "监狱管理局",
        "社科院": "社会科学院", "农科院": "农业科学院", "文史馆": "文史研究馆",
        "供销社": "供销合作社联合社", "供销合作总社": "供销合作社联合社",
        "政府办公厅职责": "政府办公厅",
    }
    for short, full in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        if text == short:
            text = full
        elif text.endswith(short) and not text.endswith(full):
            text = text[: -len(short)] + full
    text = re.sub(r"^政府(?=.)", "", text)
    return text


def canonical_province(value: str) -> str:
    """统一规则主表所属省字段。"""
    text = value.strip()
    mapping = {
        "安徽": "安徽省人民政府", "安徽省": "安徽省人民政府", "北京": "北京市人民政府", "北京市": "北京市人民政府",
        "重庆": "重庆市人民政府", "重庆市": "重庆市人民政府", "福建": "福建省人民政府", "福建省": "福建省人民政府",
        "甘肃": "甘肃省人民政府", "甘肃省": "甘肃省人民政府", "广东": "广东省人民政府", "广东省": "广东省人民政府",
        "广西": "广西壮族自治区人民政府", "广西壮族自治区": "广西壮族自治区人民政府",
        "贵州": "贵州省人民政府", "贵州省": "贵州省人民政府", "海南": "海南省人民政府", "海南省": "海南省人民政府",
        "河北": "河北省人民政府", "河北省": "河北省人民政府", "黑龙江": "黑龙江省人民政府", "黑龙江省": "黑龙江省人民政府",
        "河南": "河南省人民政府", "河南省": "河南省人民政府", "湖北": "湖北省人民政府", "湖北省": "湖北省人民政府",
        "湖南": "湖南省人民政府", "湖南省": "湖南省人民政府", "江苏": "江苏省人民政府", "江苏省": "江苏省人民政府",
        "江西": "江西省人民政府", "江西省": "江西省人民政府", "吉林": "吉林省人民政府", "吉林省": "吉林省人民政府",
        "辽宁": "辽宁省人民政府", "辽宁省": "辽宁省人民政府", "内蒙古": "内蒙古自治区人民政府", "内蒙古自治区": "内蒙古自治区人民政府",
        "宁夏": "宁夏回族自治区人民政府", "宁夏回族自治区": "宁夏回族自治区人民政府", "青海": "青海省人民政府", "青海省": "青海省人民政府",
        "山东": "山东省人民政府", "山东省": "山东省人民政府", "上海": "上海市人民政府", "上海市": "上海市人民政府",
        "陕西": "陕西省人民政府", "陕西省": "陕西省人民政府", "山西": "山西省人民政府", "山西省": "山西省人民政府",
        "四川": "四川省人民政府", "四川省": "四川省人民政府", "天津": "天津市人民政府", "天津市": "天津市人民政府",
        "新疆": "新疆维吾尔自治区人民政府", "新疆维吾尔自治区": "新疆维吾尔自治区人民政府",
        "西藏": "西藏自治区人民政府", "西藏自治区": "西藏自治区人民政府", "云南": "云南省人民政府", "云南省": "云南省人民政府",
        "浙江": "浙江省人民政府", "浙江省": "浙江省人民政府",
    }
    return mapping.get(text, "")


def link_key(url: str) -> tuple[str, str]:
    """生成用于保守核对的域名与路径键。"""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/").lower()
    return host, path


def compare_with_rule_table(inventory: list[dict[str, str]], rules: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """按省份、名称规范键、链接和高阈值相似度核对规则主表。"""
    rules_by_region: dict[str, list[dict[str, str]]] = {}
    for rule in rules:
        region = canonical_province(rule.get("所属省*", ""))
        if region:
            rules_by_region.setdefault(region, []).append(rule)

    missing: list[dict[str, str]] = []
    audit: list[dict[str, str]] = []
    for row in tqdm(inventory, desc="核对规则主表", unit="机构"):
        region = row["区域"]
        target_key = canonical_name(row["机构小类名称"], region)
        target_link = link_key(row["机构链接"])
        best_rule: dict[str, str] | None = None
        best_score = 0.0
        method = ""

        for rule in rules_by_region.get(region, []):
            rule_key = canonical_name(rule.get("机构名称", ""), region)
            if target_key and target_key == rule_key:
                best_rule, best_score, method = rule, 1.0, "名称规范键一致"
                break
            rule_links = {
                link_key(rule.get("官网链接", "")),
                link_key(rule.get("领导链接", "")),
            }
            if target_link[0] and target_link in rule_links:
                best_rule, best_score, method = rule, 1.0, "链接一致"
                break
            score = SequenceMatcher(None, target_key, rule_key).ratio() if target_key and rule_key else 0.0
            if score > best_score:
                best_rule, best_score = rule, score

        if method == "" and best_score >= 0.88 and best_rule is not None:
            method = "名称高相似度"
        elif method == "":
            best_rule = None

        audit_row = {
            **row,
            "匹配状态": "已记录" if best_rule else "缺失",
            "匹配方式": method,
            "规则主表机构": best_rule.get("机构名称", "") if best_rule else "",
            "脚本序号": best_rule.get("脚本序号", "") if best_rule else "",
            "官网链接": best_rule.get("官网链接", "") if best_rule else "",
            "领导链接": best_rule.get("领导链接", "") if best_rule else "",
            "相似度": f"{best_score:.4f}" if best_rule else f"{best_score:.4f}",
        }
        audit.append(audit_row)
        if best_rule is None:
            missing.append(row)
    return missing, audit


def deduplicate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """按区域和机构比较键去重，优先保留全称及有效链接。"""
    selected: dict[tuple[str, str], dict[str, str]] = {}
    order: list[tuple[str, str]] = []
    for row in rows:
        key = (row["区域"], canonical_name(row["机构小类名称"], row["区域"]))
        if key not in selected:
            selected[key] = row
            order.append(key)
            continue
        old = selected[key]
        old_score = len(old["机构小类名称"]) + (100 if old["机构链接"] else 0)
        new_score = len(row["机构小类名称"]) + (100 if row["机构链接"] else 0)
        if new_score > old_score:
            selected[key] = row
    return [selected[key] for key in order]


def apply_directory_links(rows: list[dict[str, str]], fetch_summary_path: Path) -> None:
    """按书签中的31个省级政府机构总目录网址填写目录链接。"""
    directory_by_region: dict[str, str] = {}
    for item in read_tsv(fetch_summary_path):
        bookmark_name = item.get("区域书签名", "").strip()
        province_name = re.sub(r"机构$", "", bookmark_name)
        region = canonical_province(province_name)
        directory_link = item.get("目录链接", "").strip()
        if region and directory_link:
            directory_by_region[region] = directory_link

    inventory_regions = {row["区域"] for row in rows}
    missing_regions = sorted(inventory_regions - directory_by_region.keys())
    if missing_regions:
        raise ValueError(f"缺少书签总目录链接：{'、'.join(missing_regions)}")

    for row in rows:
        row["目录链接"] = directory_by_region[row["区域"]]


def main(
    candidate_path: Path,
    rule_table_path: Path,
    html_dir: Path,
    fetch_summary_path: Path,
    all_output_path: Path,
    missing_output_path: Path,
    audit_output_path: Path,
    log_path: Path,
    protected_manual_data: dict[str, str],
) -> None:
    """完成全量机构表汇总、去重、规则主表核对和结果输出。"""
    logger = configure_logging(log_path)
    special_regions = {"甘肃省人民政府", "湖北省人民政府", "青海省人民政府", "上海市人民政府", "山西省人民政府", "四川省人民政府"}
    standard_rows = [row for row in read_tsv(candidate_path) if row["区域"] not in special_regions]
    rows = supplement_yunnan_current_directory(clean_standard_rows(standard_rows))

    for region, data in protected_manual_data.items():
        rows.extend(parse_manual_inventory(region, data))
    rows.extend(parse_shanghai(html_dir / "23_上海机构_www.shanghai.gov.cn.html", "https://www.shanghai.gov.cn/nw49254/index.html"))
    rows.extend(parse_shanxi(html_dir / "25_山西机构_www.shanxi.gov.cn.html", "https://www.shanxi.gov.cn/zfxxgk/zfxxgkzl/fdzdgknr/jgjj/"))
    rows.extend(parse_sichuan(html_dir / "26_四川机构_www.sc.gov.cn.html", "https://www.sc.gov.cn/10462/ptlinks/szptlinks.shtml"))

    region_order = {
        name: index
        for index, name in enumerate(
            [
                "安徽省人民政府", "北京市人民政府", "重庆市人民政府", "福建省人民政府", "甘肃省人民政府",
                "广东省人民政府", "广西壮族自治区人民政府", "贵州省人民政府", "海南省人民政府", "河北省人民政府",
                "黑龙江省人民政府", "河南省人民政府", "湖北省人民政府", "湖南省人民政府", "江苏省人民政府",
                "江西省人民政府", "吉林省人民政府", "辽宁省人民政府", "内蒙古自治区人民政府", "宁夏回族自治区人民政府",
                "青海省人民政府", "山东省人民政府", "上海市人民政府", "陕西省人民政府", "山西省人民政府",
                "四川省人民政府", "天津市人民政府", "新疆维吾尔自治区人民政府", "西藏自治区人民政府", "云南省人民政府",
                "浙江省人民政府",
            ]
        )
    }
    rows = deduplicate_rows(rows)
    rows.sort(key=lambda row: region_order.get(row["区域"], 999))
    apply_directory_links(rows, fetch_summary_path)
    rules = read_tsv(rule_table_path)
    missing, audit = compare_with_rule_table(rows, rules)

    write_inventory(all_output_path, rows)
    write_inventory(missing_output_path, missing)
    write_audit(audit_output_path, audit)
    logger.info("汇总完成：全量%d项，规则主表缺失%d项", len(rows), len(missing))
    logger.info("全量表：%s", all_output_path)
    logger.info("缺失表：%s", missing_output_path)
    logger.info("核对审计：%s", audit_output_path)


if __name__ == "__main__":
    candidate_path = resolve_project_path(r"important_people/workspace/reports/机构目录/省级政府机构候选初稿.txt", anchor=__file__, must_exist=True)
    rule_table_path = resolve_project_path(r"important_people/workspace/source_data/规则主表.txt", anchor=__file__, must_exist=True)
    html_dir = resolve_project_path(r"important_people/workspace/snapshots/机构目录/省级政府机构目录/html", anchor=__file__, must_exist=True)
    fetch_summary_path = resolve_project_path(r"important_people/workspace/reports/机构目录/省级政府机构目录抓取摘要.txt", anchor=__file__, must_exist=True)
    all_output_path = resolve_project_path(r"important_people/workspace/reports/机构目录/31个省级行政区政府机构全量表.txt", anchor=__file__)
    missing_output_path = resolve_project_path(r"important_people/workspace/reports/机构目录/31个省级行政区政府机构规则主表缺失表.txt", anchor=__file__)
    audit_output_path = resolve_project_path(r"important_people/workspace/reports/机构目录/省级机构与规则主表核对审计.txt", anchor=__file__)
    log_path = resolve_project_path(r"important_people/workspace/log/机构目录/省级政府机构全量与缺失统计.log", anchor=__file__)
    protected_manual_data = {
        "甘肃省人民政府": """
【甘肃省人民政府办公厅】
甘肃省人民政府办公厅
【甘肃省人民政府组成部门】
甘肃省发展和改革委员会
甘肃省教育厅
甘肃省科学技术厅
甘肃省工业和信息化厅
甘肃省民族事务委员会
甘肃省公安厅
甘肃省民政厅
甘肃省司法厅
甘肃省财政厅
甘肃省人力资源和社会保障厅
甘肃省自然资源厅
甘肃省生态环境厅
甘肃省住房和城乡建设厅
甘肃省交通运输厅
甘肃省水利厅
甘肃省农业农村厅
甘肃省商务厅
甘肃省文化和旅游厅
甘肃省卫生健康委员会
甘肃省退役军人事务厅
甘肃省应急管理厅
甘肃省审计厅
甘肃省人民政府外事办公室
【甘肃省人民政府直属特设机构】
甘肃省人民政府国有资产监督管理委员会
【甘肃省人民政府直属机构】
甘肃省林业和草原局
甘肃省市场监督管理局
甘肃省广播电视局
甘肃省体育局
甘肃省统计局
甘肃省人民政府研究室
甘肃省国防动员办公室
甘肃省营商环境建设局
甘肃省机关事务管理局
甘肃省医疗保障局
甘肃省地方金融管理局
【甘肃省人民政府部门管理机构】
甘肃省人民政府参事室
甘肃省数据局
甘肃省粮食和物资储备局
甘肃省能源局
甘肃省监狱管理局
甘肃省文物局
甘肃省中医药管理局
甘肃省药品监督管理局
甘肃省疾病预防控制局
甘肃省矿山安全监督管理局
【甘肃省人民政府直属事业单位】
甘肃省人民政府文史研究馆
甘肃省地方史志办公室
甘肃省社会科学院
甘肃省科学院
甘肃省农业科学院
甘肃省供销合作社联合社
甘肃省公共资源交易中心
甘肃省广播电视总台
甘肃省大数据中心
""",
        "湖北省人民政府": """
【湖北省人民政府办公厅】
湖北省人民政府办公厅
【湖北省直部门网站】
湖北省发展和改革委员会
湖北省教育厅
湖北省科学技术厅
湖北省经济和信息化厅
湖北省民族宗教事务委员会
湖北省公安厅
湖北省民政厅
湖北省司法厅
湖北省财政厅
湖北省人力资源和社会保障厅
湖北省自然资源厅
湖北省生态环境厅
湖北省住房和城乡建设厅
湖北省交通运输厅
湖北省水利厅
湖北省农业农村厅
湖北省商务厅
湖北省文化和旅游厅
湖北省卫生健康委员会
湖北省退役军人事务厅
湖北省应急管理厅
湖北省审计厅
湖北省人民政府国有资产监督管理委员会
湖北省市场监督管理局
湖北省广播电视局
湖北省体育局
湖北省统计局
湖北省医疗保障局
湖北省国防动员办公室
湖北省人民政府研究室
湖北省信访局
湖北省机关事务管理局
湖北省数据局
湖北省地方金融管理局
湖北省知识产权局
湖北省林业局
湖北省药品监督管理局
湖北省粮食局
湖北省监狱管理局
湖北省地质局
湖北省公共资源交易中心（湖北省政府采购中心）
湖北省农业事业发展中心
湖北省供销合作总社
""",
        "青海省人民政府": """
【省政府办公厅】
青海省人民政府办公厅
【组成部门】
省发展和改革委员会
省教育厅
省科学技术厅
省工业和信息化厅
省民族宗教事务委员会
省公安厅
省民政厅
省司法厅
省财政厅
省人力资源和社会保障厅
省自然资源厅
省生态环境厅
省住房和城乡建设厅
省交通运输厅
省水利厅
省农业农村厅
省商务厅
省文化和旅游厅
省卫生健康委员会
省退役军人事务厅
省应急管理厅
省审计厅
省外事办公室
【直属特设机构】
省国有资产监督管理委员会
【直属机构】
省林业和草原局
省市场监督管理局
省广播电视局
省统计局
省体育局
省医疗保障局
省国防动员办公室
省信访局
省数据局（省政务服务监督管理局）
【部门管理机构】
省直机关事务管理局
省粮食局
省能源局
省监狱管理局
省药品监督管理局
【派出机构】
三江源国家公园管理局
青海湖景区保护利用管理局
【其他机构】
省政府新闻办公室
省科协
省残联
省工商联
省红十字会
""",
    }
    main(candidate_path, rule_table_path, html_dir, fetch_summary_path, all_output_path, missing_output_path, audit_output_path, log_path, protected_manual_data)
