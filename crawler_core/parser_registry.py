from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from crawler_core.models import PersonRecord
from crawler_core import parsers_v1
from crawler_core.baidu_baike import parse_baidu_baike_leader_section_v1


ParserFunc = Callable[[dict[str, Any], str, str, Path | None], list[PersonRecord]]


PARSER_REGISTRY: dict[str, ParserFunc] = {
    "V001_css_field_pair_v1": parsers_v1.parse_strong_css_fields_v1,
    "V002_table_label_value_v1": parsers_v1.table_person_parser_v1,
    "V003_table_compound_person_v1": parsers_v1.table_compound_person_parser_v1,
    "V004_card_person_v1": parsers_v1.card_person_parser_v1,
    "V005_text_duty_colon_name_v1": parsers_v1.duty_colon_name_parser_v1,
    "V006_text_name_colon_duty_v1": parsers_v1.name_colon_duty_parser_v1,
    "V007_text_name_space_duty_v1": parsers_v1.name_space_duty_parser_v1,
    "V008_text_name_nextline_duty_v1": parsers_v1.name_nextline_duty_parser_v1,
    "V009_text_profile_paragraph_v1": parsers_v1.paragraph_profile_parser_v1,
    "V010_text_profile_detail_v1": parsers_v1.profile_detail_parser_v1,
    "V011_directory_link_v1": parsers_v1.leader_directory_link_parser_v1,
    "S001_zhejiang_gov_department_leader_card_v1": parsers_v1.zhejiang_department_leader_card_parser_v1,
    "S002_zhejiang_gov_leader_group_v1": parsers_v1.zhejiang_government_leader_group_parser_v1,
    "S003_hangzhou_gov_leader_team_v1": parsers_v1.hangzhou_leader_team_parser_v1,
    "S004_mfa_main_leader_info_v1": parsers_v1.mfa_leader_info_parser_v1,
    "S005_harbin_gov_detail_info_v1": parsers_v1.harbin_detail_info_parser_v1,
    "S006_shandong_gov_ldxx_table_v1": parsers_v1.shandong_department_ldxx_parser_v1,
    "S007_shandong_gov_leader_group_v1": parsers_v1.shandong_government_leader_group_parser_v1,
    "S008_court_main_duty_name_text_v1": parsers_v1.court_text_duty_name_parser_v1,
    "S009_mct_main_leader_group_v1": parsers_v1.mct_leader_parser_v1,
    "S010_huhhot_gov_xhr_leader_list_v1": parsers_v1.huhhot_leader_list_parser_v1,
    "S011_zhengzhou_public_leader_list_v1": parsers_v1.public_zhengzhou_leader_parser_v1,
    "S012_qingdao_gov_ldxx_table_v1": parsers_v1.qingdao_government_parser_v1,
    "S013_ce_district_leader_list_v1": parsers_v1.ce_district_leader_parser_v1,
    "S014_ce_district_city_four_leaders_table_v1": parsers_v1.ce_city_four_leaders_table_parser_v1,
    "S015_moj_main_leader_list_v1": parsers_v1.moj_leader_parser_v1,
    "S016_neac_main_leader_card_v1": parsers_v1.neac_leader_parser_v1,
    "S017_neac_main_society_org_people_v1": parsers_v1.neac_society_org_people_parser_v1,
    "S018_moe_main_department_leader_v1": parsers_v1.moe_leader_parser_v1,
    "S019_cppcc_main_role_group_v1": parsers_v1.cppcc_role_group_parser_v1,
    "S020_fuzhou_xinfang_name_duty_split_v1": parsers_v1.fuzhou_xinfang_leader_parser_v1,
    "S021_cas_main_leader_group_v1": parsers_v1.cas_leader_group_parser_v1,
    "S022_npc_main_committee_role_list_v1": parsers_v1.npc_committee_role_parser_v1,
    "S023_chongqing_jgzn_card_name_duty_v1": parsers_v1.chongqing_jgzn_card_name_duty_parser_v1,
    "S024_hlj_card_person_clean_duty_prefix_v1": parsers_v1.hlj_card_person_parser_v1,
    "S025_yinchuan_name_colon_parenthesized_duty_v1": parsers_v1.yinchuan_name_colon_parenthesized_duty_parser_v1,
    "S026_qinghai_slt_name_nextline_clean_duty_prefix_v1": parsers_v1.qinghai_slt_name_nextline_clean_duty_prefix_parser_v1,
    "S027_baidu_baike_leader_section_v1": parse_baidu_baike_leader_section_v1,
}

def resolve_parser_name(parser_name: str) -> str:
    """返回正式 V/S 解析器名称。"""
    return str(parser_name or "").strip()


def parse_with_registered_parser(
    rule: dict[str, Any],
    html: str,
    final_url: str = "",
    snapshot_path: Path | None = None,
) -> list[PersonRecord]:
    parser_name = resolve_parser_name(str(rule.get("parser", "V001_css_field_pair_v1") or "V001_css_field_pair_v1"))
    if parser_name == "skip":
        return []
    parser = PARSER_REGISTRY.get(parser_name)
    if parser is None:
        parser = parsers_v1.parse_generic_confirmed_page
    local_rule = dict(rule)
    local_rule["parser"] = parser_name or "V001_css_field_pair_v1"
    return parser(local_rule, html, final_url, snapshot_path)
