from __future__ import annotations

import re
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

PAGE_RULE = {'rule_id': '0353',
 'domain': 'ct.ah.gov.cn',
 'page_type': '人物列表完整页',
 'structure_group': '',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'raw_http',
 'extract_mode': 'list_direct',
 'collector': 'raw_http',
 'parser': 'page_inline_ah_public_title_suffix_name_v1',
 'leader_region_selector': '#zdgkList ul.xxgk_nav_list li',
 'name_selector': '标题末尾人名',
 'duty_selector': '标题去除机构前缀和末尾人名',
 'detail_link_selector': 'a[href]',
 'content_scope': {'start_anchor': '', 'end_anchor': '', 'include_selectors': ['#zdgkList'], 'exclude_selectors': []},
 'detail_strategy': {'required': False,
                     'mode': 'none',
                     'detail_collector_type': 'static_http',
                     'detail_link_selector': '',
                     'detail_parser': '',
                     'detail_name_selector': '',
                     'detail_duty_selector': '',
                     'detail_content_selector': '',
                     'max_detail_links': 50},
 'risk_flag': '入口查询参数包含catId，必须保留原始HTTP响应，禁止跟随脚本跳转丢失目标栏目',
 'confidence': 'high',
 'profile_reusable': '',
 'profile_judgement': '',
 'filter_policy': 'strong_no_wordlist',
 'locator_strategy': 'css+title_suffix_split',
 'locator': {'css': {'leader_region_selector': '#zdgkList ul.xxgk_nav_list li',
                     'name_selector': '标题末尾人名',
                     'duty_selector': '标题去除机构前缀和末尾人名',
                     'detail_link_selector': 'a[href]',
                     'content_scope': {'start_anchor': '',
                                       'end_anchor': '',
                                       'include_selectors': ['#zdgkList'],
                                       'exclude_selectors': []}}},
 'api': {'enabled': False, 'reason': '在线页面已有完整政务公开列表'}}


COMMON_SURNAMES = set(
    '赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武符刘詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧沃利蔚越隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公海'
)


def clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def split_title(title: str) -> tuple[str, str]:
    title = clean_text(title)
    title = re.sub(r'^\s*(?:安徽)?省文化和旅游厅', '', title)
    for length in range(4, 1, -1):
        candidate = title[-length:]
        if re.fullmatch(r'[\u4e00-\u9fa5·]{2,4}', candidate) and candidate[0] in COMMON_SURNAMES:
            duty = clean_text(title[:-length]).rstrip('，、：:；;')
            if duty:
                return candidate, duty
    return '', ''


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'lxml')
    rows = []
    seen = set()
    for item in soup.select('#zdgkList ul.xxgk_nav_list li'):
        link = item.select_one('a[href]')
        if not link:
            continue
        title = clean_text(link.get_text(' ', strip=True))
        if '文化和旅游厅' not in title:
            continue
        name, duty = split_title(title)
        if not name or not duty:
            continue
        href = str(link.get('href', '')).strip()
        detail_url = ''
        if href and not href.lower().startswith(('#', 'javascript:')):
            candidate_url = urljoin(final_url or page_rule['url'], href)
            if candidate_url.rstrip('/') != (final_url or page_rule['url']).rstrip('/'):
                detail_url = candidate_url
        key = (name, duty, detail_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'duty': duty,
            'detail_url': detail_url,
            'evidence': duty,
            'confidence': 'high',
            'parser': 'page_inline_ah_public_title_suffix_name_v1',
            'selector_summary': 'leader=#zdgkList ul.xxgk_nav_list li；title=a[href]；name=标题末尾人名；duty=标题去机构前缀和人名；api_enabled=False',
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
