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

PAGE_RULE = {'rule_id': '0380',
 'domain': 'czt.gd.gov.cn',
 'page_type': '人物表格页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'collector': 'static_http',
 'parser': 'page_inline_guangdong_finance_profile_paragraph_v1',
 'leader_region_selector': '.article-content p',
 'name_selector': '段落中性别标记前的人名',
 'duty_selector': '段落中人名前的职务文本',
 'detail_link_selector': '',
 'content_scope': {'start_anchor': '',
                   'end_anchor': '',
                   'include_selectors': ['.article-content'],
                   'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '.article-content',
                     'max_detail_links': 50},
 'risk_flag': '第二轮定向修复',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css+regex',
 'locator': {'css': {'leader_region_selector': '.article-content p',
                     'name_selector': '段落中性别标记前的人名',
                     'duty_selector': '段落中人名前的职务文本',
                     'detail_link_selector': '',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['.article-content'],
                                       'exclude_selectors': []}},
             'api': {'enabled': False, 'reason': '在线静态 HTML 正文段落已直出领导简介'}}}


def clean_text(value: str) -> str:
    text = re.sub(r'\s+', ' ', value or '').strip()
    text = re.sub(r'\s*([、，,；;：:])\s*', r'\1', text)
    return text


def normalize_duty(value: str) -> str:
    duty = clean_text(value).rstrip('。')
    return clean_text(duty).strip('，、；;')


COMMON_SURNAMES = set(
    '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜'
    '戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐'
    '费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平'
    '黄和穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成戴谈宋庞熊纪舒屈项祝董梁'
    '杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍'
    '虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程'
    '邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧'
    '隗山谷车侯宓蓬全班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶'
    '幸司韶黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘'
    '党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀浦尚农温别'
    '庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡'
    '国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空'
    '曾毋沙乜养鞠须丰巢关蒯相查荆红游竺权逯盖益桓公'
)


def parse_profile_line(text: str) -> tuple[str, str] | None:
    line = clean_text(text)
    match = re.match(r'(?P<head>.+?)，(?P<gender>男|女)，', line)
    if not match:
        return None
    head = re.sub(r'\s+', '', match.group('head'))
    name = ''
    for length in (4, 3):
        candidate = head[-length:]
        if len(candidate) == length and re.fullmatch(r'[\u4e00-\u9fa5·]+', candidate) and candidate[0] in COMMON_SURNAMES:
            name = candidate
            break
    if not name:
        name = head[-2:]
    duty = normalize_duty(head[:-len(name)])
    if not duty:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for paragraph in soup.select('.article-content p'):
        parsed = parse_profile_line(paragraph.get_text(' ', strip=True))
        if not parsed:
            continue
        name, duty = parsed
        key = (name, duty)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': '',
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_guangdong_finance_profile_paragraph_v1',
            'selector_summary': 'leader=.article-content p；name=姓名位于“，男/女，”前；duty=姓名前文本；api_enabled=False',
        })
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
