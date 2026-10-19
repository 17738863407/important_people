from __future__ import annotations

import importlib.util
import re
from datetime import datetime
from pathlib import Path
from types import ModuleType

from tqdm import tqdm

from crawler_core.paths import resolve_path_argument, timestamped_output_path


def load_cleaning_module(script_path: Path) -> ModuleType:
    """加载清理阶段脚本，复用十二列读写和基础文本函数。"""
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到清理脚本：{script_path}")
    spec = importlib.util.spec_from_file_location("duty_cleaning", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载清理脚本：{script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_base_organization(value: str) -> str:
    """提取当前行机构主名称，移除状态括号和关联机构部分。"""
    text = re.sub(r"[（(][^（）()]*[）)]", "", re.sub(r"\s+", "", str(value or "")))
    return re.split(r"[—–－-]|[:：]", text, maxsplit=1)[0].strip()


def infer_context(row: dict[str, str]) -> tuple[str, str, str, str]:
    """取得当前机构、省、市和州级地域。"""
    base_org = clean_base_organization(row.get("机构", ""))
    province = row.get("所属省*", "").strip()
    if province == "全国":
        province = ""
    known_provinces = (
        "北京市", "天津市", "上海市", "重庆市", "河北省", "山西省", "辽宁省", "吉林省",
        "黑龙江省", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省", "河南省",
        "湖北省", "湖南省", "广东省", "海南省", "四川省", "贵州省", "云南省", "陕西省",
        "甘肃省", "青海省", "内蒙古自治区", "广西壮族自治区", "西藏自治区",
        "宁夏回族自治区", "新疆维吾尔自治区", "香港特别行政区", "澳门特别行政区",
    )
    if not province:
        province = next((item for item in known_provinces if base_org.startswith(item)), "")
    if not province:
        provincial_party_match = re.match(r"([\u4e00-\u9fff]{2,8})省委", base_org)
        if provincial_party_match:
            province = provincial_party_match.group(1) + "省"
    if not province:
        municipality_party_match = re.match(r"(北京|天津|上海|重庆)市委", base_org)
        if municipality_party_match:
            province = municipality_party_match.group(1) + "市"
    city = row.get("所属市", "").strip()
    if not city and province in {"北京市", "天津市", "上海市", "重庆市"}:
        city = province
    if not city:
        organization = base_org[len(province) :] if province and base_org.startswith(province) else base_org
        match = re.match(
            r"([\u4e00-\u9fff]{2,8}市)(?=委|人大|人民政府|政府|政协|纪委|监委|公安|教育|交通|农业|"
            r"医疗|卫生|发展|司法|城市|市场|应急|政务|文化|水利|生态|自然|财政|$)",
            organization,
        )
        city = match.group(1) if match else ""
    prefecture_match = re.match(
        r"([\u4e00-\u9fff]{2,12}?(?:自治州|州))(?=委|人大|人民政府|政府|政协|纪委|监委|$)",
        base_org,
    )
    prefecture = prefecture_match.group(1) if prefecture_match else ""
    return base_org, province, city, prefecture


def build_context_subjects(row: dict[str, str], base_org: str, province: str, city: str) -> dict[str, str]:
    """构造只补缺失成分、不改变简称性质的当前行主体映射。"""
    subjects: dict[str, str] = {}
    raw_organization = re.sub(r"\s+", "", row.get("机构", ""))
    parts = [part for part in re.split(r"[—–－:：]", raw_organization) if part]
    for prefix in sorted({province, city}, key=len, reverse=True):
        if prefix and base_org.startswith(prefix) and len(base_org) > len(prefix):
            subjects[base_org[len(prefix) :]] = base_org
    for suffix in (
        "财政厅", "公安厅", "教育厅", "审计厅", "司法厅", "商务厅", "自然资源厅",
        "农业农村厅", "应急管理厅",
    ):
        if base_org.endswith(suffix):
            subjects[suffix] = base_org
    for short_subject, full_suffix in (
        ("厅", "厅"),
        ("局", "局"),
        ("委", "委员会"),
        ("院", "院"),
        ("馆", "馆"),
        ("校", "学校"),
    ):
        if base_org.endswith(full_suffix):
            subjects[short_subject] = base_org
    if base_org.endswith("管理委员会"):
        area_name = base_org.removesuffix("管理委员会")
        subjects["管委会"] = area_name + "管委会"
    if len(parts) >= 2:
        primary = parts[0]
        parent_match = re.match(r"^(.+?(?:部|署|总局|委员会))", primary)
        parent = parent_match.group(1) if parent_match else primary
        for secondary in parts[1:]:
            full_secondary = secondary if secondary.startswith(parent) else parent + secondary
            subjects[secondary] = full_secondary
            if "巡视工作领导小组办公室" in secondary or secondary == "巡视办":
                subjects["巡视办"] = parent + "巡视办"
    return dict(sorted(subjects.items(), key=lambda item: len(item[0]), reverse=True))


def build_named_alias_subjects(base_org: str) -> dict[str, str]:
    """根据机构全称生成保留简称的完整简称主体。"""
    subjects: dict[str, str] = {}
    alias_pairs = (
        ("国有资产监督管理委员会", "国资委"),
        ("发展和改革委员会", "发改委"),
        ("卫生健康委员会", "卫健委"),
        ("住房和城乡建设局", "住建局"),
        ("工业和信息化局", "工信局"),
    )
    for full_suffix, alias in alias_pairs:
        if not base_org.endswith(full_suffix):
            continue
        prefix = base_org[: -len(full_suffix)]
        if prefix.endswith("人民政府"):
            prefix = prefix.removesuffix("人民政府")
        subjects[alias] = prefix + alias
    if base_org.endswith("管理委员会"):
        area_name = base_org.removesuffix("管理委员会")
        subjects["管委会"] = area_name + "管委会"
        compact_area_name = area_name.removeprefix("北京")
        if compact_area_name:
            subjects[compact_area_name + "党工委"] = area_name + "党工委"
    return dict(sorted(subjects.items(), key=lambda item: len(item[0]), reverse=True))


def expand_leading_subject(token: str, subjects: dict[str, str]) -> str:
    """仅在职务片段开头补入当前行能够证明的缺失主体成分。"""
    for short_subject, completed_subject in subjects.items():
        if token.startswith(short_subject) and not token.startswith(completed_subject):
            remainder = token[len(short_subject) :]
            if short_subject in {"厅", "局", "院", "馆", "校"} and not remainder.startswith(
                ("党组", "党委", "纪委", "党工委", "机关", "总", "一级", "二级", "三级", "四级")
            ):
                return completed_subject + token
            return completed_subject + remainder
    return token


def complete_geographic_placeholders(token: str, province: str, city: str) -> str:
    """补全“省、市、自治区”等地域占位词，同时保留机构简称。"""
    text = token
    if province:
        if text.startswith("自治区") and province.endswith("自治区"):
            text = province + text[len("自治区") :]
        elif text.startswith("省") and province.endswith("省") and not re.match(r"^省长(?:候选人)?$", text):
            text = province + text[1:]
        elif text.startswith("区") and province.endswith("自治区") and not re.match(r"^区长$", text):
            text = province + text[1:]
    if city:
        if text.startswith("市纪委市监委"):
            text = city + "纪委" + city + "监委" + text[len("市纪委市监委") :]
        elif text.startswith("市纪委监委"):
            text = city + "纪委监委" + text[len("市纪委监委") :]
        elif text.startswith("市") and not re.match(r"^市长$", text):
            text = city + text[1:]
        text = re.sub(r"驻市(?=[\u4e00-\u9fff]{2,12}(?:局|委|委员会))", "驻" + city, text)
    return text


def remove_redundant_province_before_locality(token: str, province: str, city: str) -> str:
    """所属市（含自治州等地级地域）明确时，删除其前面可由该地域反推的省名。"""
    if not province or not city:
        return token
    full_prefix = province + city
    if token.startswith(full_prefix):
        return token[len(province) :]
    return token


def identify_geographic_placeholder(token: str) -> str:
    """识别确实位于机构主体开头的地域占位词，避免误判“市场”等普通词语。"""
    match = re.match(
        r"^(自治区|省|市|区)(?=(?:党委|党工委|政府|人民政府|人大|政协|纪委|监委|"
        r"公安|教育|财政|司法|生态|市场|应急|水利|医疗|卫生|发展|城市|自然|政务|"
        r"交通|农业|审计|商务|住建|国资|发改|工信|文旅|民政|统计|信访))",
        token,
    )
    return match.group(1) if match else ""


def has_placeholder_context(placeholder: str, province: str, city: str) -> bool:
    """判断当前行是否具备把地域占位词安全补全为专名的上下文。"""
    if placeholder in {"省", "自治区"}:
        return bool(province)
    if placeholder == "市":
        return bool(city)
    if placeholder == "区":
        return bool(province or city)
    return False


def complete_relative_institution(
    token: str,
    current_subject: str,
    base_org: str,
    province: str,
    city: str,
) -> str:
    """补全无地域机构、当前机构内部单位及党委组成部门的相对主体。"""
    token = re.sub(
        r"(厅|局|委|院|部|署|馆|校)\1(?=(?:党组|党委|纪委|党工委|机关党委))",
        r"\1",
        token,
    )
    if province == "新疆维吾尔自治区":
        if token.startswith("新疆兵团"):
            token = "新疆生产建设兵团" + token[len("新疆兵团") :]
        elif token.startswith("兵团"):
            token = "新疆生产建设兵团" + token[len("兵团") :]
    if token.startswith(("中共中央", "共青团中央", "国务院", "中央", "国家", "全国", "中国", "最高人民", "新疆生产建设兵团")):
        return token
    if province and token.startswith(province):
        return token
    if city and token.startswith(city):
        return token

    # 药监局、知识产权局通常使用省级简称；地震局按当前页面地域层级补足。
    if token.startswith(("药监局", "知识产权局")) and province:
        return province + token
    if token.startswith("地震局"):
        jurisdiction = city or province
        return jurisdiction + token if jurisdiction else token

    pure_leadership_titles = {
        "常务副馆长": ("馆",),
        "常务副院长": ("院", "学院"),
        "第一副院长": ("院", "学院"),
    }
    if token in pure_leadership_titles:
        expected_suffixes = pure_leadership_titles[token]
        subject = current_subject if current_subject.endswith(expected_suffixes) else base_org
        return subject + token if subject else token

    relative_units = (
        "常务委员会", "常委会", "办公厅", "调查统计司", "医政司", "新闻局",
        "队伍建设指导部", "宣传教育培训部", "党支部",
    )
    for unit in relative_units:
        if not token.startswith(unit):
            continue
        remainder = token[len(unit) :]
        if base_org.endswith(unit):
            return base_org + remainder
        if unit == "常委会" and base_org.endswith("人大常委会"):
            return base_org + remainder
        if unit == "办公厅" and current_subject.endswith(("委", "政府", "人大", "政协")):
            return current_subject + token
        sibling_units = ("办公厅", "调查统计司", "医政司", "新闻局")
        if unit in sibling_units:
            for existing_unit in sibling_units:
                if base_org.endswith(existing_unit):
                    return base_org[: -len(existing_unit)] + token
        return base_org + token if base_org else token

    # 组织部、宣传部、统战部等是党委组成部门，应继承同组党委主体。
    party_department_pattern = re.compile(
        r"^(?:组织部|宣传部|统战部|政法委|社会工作部|编办|网信办|办公厅|办公室)"
    )
    if party_department_pattern.match(token):
        party_subject = current_subject if current_subject.endswith("委") else ""
        if not party_subject and base_org.endswith("委"):
            party_subject = base_org
        if party_subject:
            return party_subject + token

    # 这些名称表达的是当前机构内部部门或所属中心，必须写明隶属主体。
    internal_unit_pattern = re.compile(
        r"^(?:政治部|机关党委|离退休干部局|非税收入核算中心|.+(?:处|科|室|中心|服务中心|保障中心))"
    )
    if internal_unit_pattern.match(token):
        parent_subject = base_org or current_subject
        if parent_subject and not token.startswith(parent_subject):
            return parent_subject + token
    return token


def complete_municipality_prefix(token: str, province: str) -> str:
    """为直辖市区县机构补入直辖市名称。"""
    municipalities = {"北京市", "天津市", "上海市", "重庆市"}
    if province not in municipalities or token.startswith(province):
        return token
    if re.match(r"^[\u4e00-\u9fff]{1,8}(?:区|县)(?:委|政府|人大|政协|纪委|监委)", token):
        return province + token
    return token


def extract_jurisdiction(value: str, level: str, province: str) -> str:
    """从同组已完成职务或当前机构提取区县名称。"""
    matches = re.findall(
        rf"((?:北京|天津|上海|重庆)市)?([\u4e00-\u9fff]{{1,10}}{level})(?=委|政府|人大|政协|纪委|监委)",
        value,
    )
    if not matches:
        return ""
    municipality, local_name = matches[-1]
    if municipality:
        return municipality + local_name
    if province in {"北京市", "天津市", "上海市", "重庆市"}:
        return province + local_name
    return local_name


def complete_local_level_placeholder(
    token: str,
    completed_tokens: list[str],
    base_org: str,
    province: str,
) -> str:
    """用同组最近出现的区县名称补全“区某机构”“县某机构”。"""
    for level in ("区", "县"):
        if not token.startswith(level):
            continue
        if re.match(rf"^{level}长(?:候选人)?$", token):
            continue
        jurisdiction = extract_jurisdiction("、".join([*completed_tokens, base_org]), level, province)
        if jurisdiction:
            return jurisdiction + token[len(level) :]
    return token


def complete_administrative_head(
    token: str,
    completed_tokens: list[str],
    base_org: str,
    province: str,
    city: str,
    prefecture: str,
) -> str:
    """为省市州区县行政首长职务补入明确地域。"""
    if token in {"省长", "代省长", "代理省长", "副省长", "常务副省长", "省长候选人"} and province:
        return province + token
    if token in {"市长", "代市长", "代理市长", "副市长", "常务副市长", "市长候选人"} and city:
        return city + token
    if token in {"州长", "代州长", "代理州长", "副州长", "常务副州长", "州长候选人"} and prefecture:
        return prefecture + token
    for level in ("区", "县"):
        if token not in {
            f"{level}长",
            f"代{level}长",
            f"代理{level}长",
            f"副{level}长",
            f"常务副{level}长",
            f"{level}长候选人",
        }:
            continue
        jurisdiction = extract_jurisdiction("、".join([*completed_tokens, base_org]), level, province)
        if jurisdiction:
            return jurisdiction + token
    return token


def normalize_collapsed_administrative_head(token: str) -> str:
    """恢复原文中与行政区末字重叠的行政首长职务层级。"""
    if token.startswith(("常务", "副", "代", "代理")):
        return token
    for level in ("省", "市", "区", "县"):
        match = re.match(rf"^(.+{level})长(候选人)?$", token)
        if match:
            jurisdiction = match.group(1)
            if any(
                marker in jurisdiction
                for marker in ("政府", "人民", "党委", "党组", "纪委", "监委", "常委", "副", "常务", "代理")
            ):
                return token
            candidate_suffix = match.group(2) or ""
            return jurisdiction + level + "长" + candidate_suffix
    return token


def build_stationed_target(base_org: str, province: str, city: str) -> str:
    """生成派驻纪检监察组使用的省级、市级或中央目标机构名称。"""
    if city and base_org.startswith(city):
        return "市" + base_org[len(city) :]
    if province and base_org.startswith(province):
        level_word = "省" if province.endswith("省") else "自治区" if province.endswith("自治区") else "市"
        return level_word + base_org[len(province) :]
    return base_org


def complete_stationed_discipline_subject(
    token: str,
    base_org: str,
    province: str,
    city: str,
) -> str:
    """将“驻厅/委/局”等相对表述补为纪委监委派驻机构的完整职务。"""
    if "驻" not in token or not re.search(r"纪检(?:监察)?组", token):
        return token

    group_match = re.search(r"纪检(?:监察)?组", token)
    if group_match is None:
        return token
    group_name = group_match.group(0)
    title_suffix = token[group_match.end() :]

    if re.match(r"^中央纪委国家监委驻.+纪检(?:监察)?组$", base_org):
        return base_org + title_suffix

    stationed_match = re.search(r"驻(?:省|市|自治区)?(?:厅|委|局|部|院|办|会|署)(?=纪检)", token)
    if stationed_match is None:
        return token

    target = build_stationed_target(base_org, province, city)
    if city and base_org.startswith(city):
        dispatching_authority = city + "纪委监委"
    elif province:
        dispatching_authority = province + "纪委监委"
    else:
        dispatching_authority = "中央纪委国家监委"
    return dispatching_authority + "驻" + target + group_name + title_suffix


def token_has_explicit_subject(token: str) -> bool:
    """判断职务片段是否已经具有可独立识别的任职主体。"""
    if re.match(r"^(?:中共中央|共青团中央|国务院|中央|国家|全国|中国|最高人民|新疆生产建设兵团|[\u4e00-\u9fff]{2,12}(?:省|市|区|县|自治州|自治区|特别行政区))", token):
        return True
    if re.match(r"^(?:党组|党委|纪委|党工委|机关党委|直属党委|分党组|直属机关|驻|派驻)", token):
        return False
    markers = (
        "巡视工作领导小组办公室", "人民代表大会常务委员会", "人民检察院", "人民法院",
        "管理委员会", "委员会", "办公室", "办公厅", "研究院", "研究所", "研究会",
        "人民政府", "党工委", "党委", "党组", "纪委", "监委", "政协", "人大",
        "大学", "学院", "学校", "医院", "中心", "总局", "厅", "局", "部", "署",
        "院", "馆", "宫", "站", "所", "司", "联合会", "联谊会", "协会", "学会", "学社", "同盟", "通讯社", "社",
        "科协", "调查队", "总队",
        "公司", "集团", "银行", "出版社", "总社", "电视台", "报社", "管委会", "发改委", "国资委",
        "卫健委", "住建局", "工信局",
    )
    for marker in markers:
        position = token.find(marker)
        if position >= 2:
            return True
    return False


def extract_subject(token: str, title_terms: tuple[str, ...]) -> str:
    """从完整职务片段中提取供后续孤立职务继承的主体。"""
    for title in sorted(set(title_terms), key=len, reverse=True):
        if not token.endswith(title) or len(token) <= len(title):
            continue
        subject = token[: -len(title)]
        subject = re.sub(r"(?:常务副|副|代|代理)$", "", subject)
        subject = re.sub(r"(?:党委|党组|党工委|机关党委|直属党委|分党组)$", "", subject)
        if subject and token_has_explicit_subject(subject + "负责人"):
            return subject
    return ""


def complete_row_duties(
    row: dict[str, str],
    cleaning_module: ModuleType,
) -> tuple[dict[str, str], list[str]]:
    """使每个职务片段具有明确主体，同时保留原有机构简称。"""
    output = dict(row)
    duty = row.get("职务*", "").strip()
    if not duty:
        return output, []
    config = cleaning_module.build_runtime_config()
    title_terms = tuple(config["title_terms"])
    base_org, province, city, prefecture = infer_context(row)
    context_subjects = build_context_subjects(row, base_org, province, city)
    named_alias_subjects = build_named_alias_subjects(base_org)
    completed_tokens: list[str] = []
    current_subject = ""
    active_city = city
    reasons: list[str] = []
    for original_token in [part for part in duty.split("、") if part]:
        normalized_token = normalize_collapsed_administrative_head(original_token)
        normalized_token = complete_stationed_discipline_subject(
            normalized_token,
            base_org,
            province,
            city,
        )
        if city and not normalized_token.startswith(city):
            shortened_city_forms = [city[index:] for index in range(1, len(city) - 1) if len(city[index:]) >= 2]
            shortened_city = next(
                (candidate for candidate in shortened_city_forms if normalized_token.startswith(candidate)),
                "",
            )
            if shortened_city:
                normalized_token = city + normalized_token[len(shortened_city) :]
        city_match = None
        if not normalized_token.startswith(("市", "省", "自治区")):
            city_match = re.match(
                r"([\u4e00-\u9fff]{2,8}?市)(?=委|政府|人民政府|人大|政协|纪委|监委|"
                r"公安|教育|财政|司法|生态|市场|应急|水利|医疗|卫生|发展|城市|自然|政务|"
                r"常务副市长|副市长|市长|代市长|代理市长)",
                normalized_token,
            )
        if city_match:
            candidate_city = city_match.group(1)
            if city and city.endswith(candidate_city):
                if candidate_city != city and normalized_token.startswith(candidate_city):
                    normalized_token = city + normalized_token[len(candidate_city) :]
                active_city = city
            else:
                active_city = candidate_city
        token = normalized_token
        token = complete_geographic_placeholders(token, province, active_city)
        token = complete_municipality_prefix(token, province)
        token = complete_local_level_placeholder(token, completed_tokens, base_org, province)
        token = expand_leading_subject(token, named_alias_subjects)
        token = expand_leading_subject(token, context_subjects)
        token = complete_administrative_head(token, completed_tokens, base_org, province, active_city, prefecture)
        token = complete_relative_institution(token, current_subject, base_org, province, active_city)
        if not token_has_explicit_subject(token):
            if token.startswith(("党组", "党委", "纪委", "党工委", "机关党委", "直属党委", "分党组")):
                party_subject = current_subject
                if base_org and party_subject in {base_org + suffix for suffix in ("厅", "局", "委", "院", "馆", "校")}:
                    party_subject = base_org
                if party_subject and not re.search(r"(?:纪检监察组|纪检组|政治部|中心|处|科|室)$", party_subject):
                    subject = party_subject
                else:
                    subject = base_org or current_subject
            else:
                if current_subject and not re.search(r"(?:党支部|纪检监察组|纪检组|政治部|中心|处|科|室)$", current_subject):
                    subject = current_subject
                else:
                    subject = base_org or current_subject
            if subject:
                token = subject + token
        completed_token = token
        token = remove_redundant_province_before_locality(token, province, city)
        explicit_subject = extract_subject(token, title_terms)
        if explicit_subject:
            current_subject = explicit_subject
        completed_tokens.append(token)
        if completed_token != original_token:
            reasons.append(f"主体补全：{original_token}——{completed_token}")
        if token != completed_token:
            reasons.append(f"省级前缀去冗余：{completed_token}——{token}")
        placeholder = identify_geographic_placeholder(token)
        if placeholder and not has_placeholder_context(placeholder, province, active_city):
            reasons.append(f"地域上下文不足，保留网页原文：{token}")
    output["职务*"] = "、".join(dict.fromkeys(completed_tokens))
    return output, reasons


def find_completion_errors(duty: str, province: str, city: str) -> list[str]:
    """检查有可靠上下文却仍未完成补全的职务片段。"""
    errors: list[str] = []
    for token in [part for part in duty.split("、") if part]:
        placeholder = identify_geographic_placeholder(token)
        if placeholder and has_placeholder_context(placeholder, province, city):
            errors.append(f"职务片段仍含可补全地域占位词：{token}")
        if not token_has_explicit_subject(token):
            errors.append(f"职务片段仍缺少主体：{token}")
    return errors


def build_audit_row(
    line_number: int,
    source: dict[str, str],
    output: dict[str, str],
    reasons: list[str],
) -> dict[str, str]:
    """构造补全阶段审计行。"""
    return {
        "行号": str(line_number),
        "姓名*": source.get("姓名*", ""),
        "补全前职务*": source.get("职务*", ""),
        "补全后职务*": output.get("职务*", ""),
        "机构": source.get("机构", ""),
        "脚本序号": source.get("脚本序号", ""),
        "审计原因": "；".join(reasons),
    }


def validate_completed_rows(
    source_path: Path,
    output_path: Path,
    cleaning_module: ModuleType,
) -> list[str]:
    """验证补全阶段只修改职务列且每个职务片段主体完整。"""
    config = cleaning_module.build_runtime_config()
    source_headers, source_rows = cleaning_module.read_rows(source_path)
    output_headers, output_rows = cleaning_module.read_rows(output_path)
    errors: list[str] = []
    if source_headers != config["headers"] or output_headers != config["headers"]:
        errors.append("表头不是规定的十二列或列序错误")
    if len(source_rows) != len(output_rows):
        errors.append(f"行数不一致：输入{len(source_rows)}，输出{len(output_rows)}")
    protected_fields = [header for header in config["headers"] if header != "职务*"]
    for line_number, (source, output) in enumerate(zip(source_rows, output_rows), start=2):
        for field in protected_fields:
            if source.get(field, "") != output.get(field, ""):
                errors.append(f"第{line_number}行非目标字段被修改：{field}")
        _, province, city, _ = infer_context(output)
        errors.extend(
            f"第{line_number}行{message}"
            for message in find_completion_errors(output.get("职务*", ""), province, city)
        )
    return errors


def process_all_rows(
    input_path: Path,
    output_path: Path,
    audit_path: Path,
    log_path: Path,
    cleaning_module: ModuleType,
) -> None:
    """逐行补全全部职务片段，单行失败时保留清理结果。"""
    config = cleaning_module.build_runtime_config()
    headers, rows = cleaning_module.read_rows(input_path)
    if headers != config["headers"]:
        raise ValueError(f"输入表头不符合十二列契约：{headers}")
    outputs: list[dict[str, str]] = []
    audits: list[dict[str, str]] = []
    for line_number, row in enumerate(tqdm(rows, desc="职务主体补全", unit="行"), start=2):
        try:
            output, reasons = complete_row_duties(row, cleaning_module)
        except Exception as error:
            output = dict(row)
            reasons = [f"主体补全失败，保留清理结果：{error}"]
        outputs.append(output)
        if reasons:
            audits.append(build_audit_row(line_number, row, output, reasons))
    audit_headers = list(build_audit_row(0, {}, {}, []).keys())
    cleaning_module.write_rows(output_path, headers, outputs)
    cleaning_module.write_rows(audit_path, audit_headers, audits)
    cleaning_module.write_log(log_path, f"输入记录：{len(rows)}")
    cleaning_module.write_log(log_path, f"发生主体补全或异常的记录：{len(audits)}")
    validation_errors = validate_completed_rows(input_path, output_path, cleaning_module)
    cleaning_module.write_log(log_path, f"全量质量门禁错误：{len(validation_errors)}")
    if validation_errors:
        raise ValueError(f"补全质量门禁未通过，共{len(validation_errors)}项：{'；'.join(validation_errors[:20])}")
    cleaning_module.write_log(log_path, f"补全结果：{output_path}")
    cleaning_module.write_log(log_path, f"审计报告：{audit_path}")


def build_output_paths(project_dir: Path) -> tuple[Path, Path, Path]:
    """构造补全结果、审计报告和日志路径。"""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        project_dir / "职务规范3：补全.txt",
        timestamped_output_path(
            project_dir / "workspace" / "reports" / "职务规范3：补全审计报告.txt",
            run_timestamp,
        ),
        timestamped_output_path(
            project_dir / "workspace" / "log" / "职务规范3：补全日志.txt",
            run_timestamp,
        ),
    )


def main(
    input_path: str | Path,
    project_dir: str | Path,
    cleaning_script_path: str | Path,
) -> None:
    """统一入口：为每个已清理职务补入明确主体。"""
    input_path = resolve_path_argument(input_path, anchor=__file__, must_exist=True)
    project_dir = resolve_path_argument(project_dir, anchor=__file__, must_exist=True)
    cleaning_script_path = resolve_path_argument(
        cleaning_script_path, anchor=__file__, must_exist=True
    )
    if not input_path.is_file():
        raise FileNotFoundError(f"未找到清理结果：{input_path}")
    if not project_dir.is_dir():
        raise NotADirectoryError(f"未找到项目根目录：{project_dir}")
    cleaning_module = load_cleaning_module(cleaning_script_path)
    output_path, audit_path, log_path = build_output_paths(project_dir)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("输出路径不得覆盖输入文件")
    process_all_rows(input_path, output_path, audit_path, log_path, cleaning_module)
    print(f"补全结果：{output_path}")
    print(f"审计报告：{audit_path}")
    print(f"运行日志：{log_path}")


if __name__ == "__main__":
    input_path_value = r"important_people/职务规范2：清理.txt"
    project_dir_value = r"important_people"
    cleaning_script_path_value = r"important_people/script3-职务规范2-清理.py"
    main(input_path=input_path_value, project_dir=project_dir_value, cleaning_script_path=cleaning_script_path_value)
