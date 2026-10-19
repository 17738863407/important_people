from __future__ import annotations
import sys
from pathlib import Path

def resolve_project_dir()->Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent/"crawler_core").is_dir(): return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def build_page_rule(rule_id:str)->dict:
    """基于已核验的领导名单图片构造 DeepSeek 视觉抽取规则。"""
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.vision_llm import build_vision_page_rule
    rule=build_vision_page_rule(rule_id=rule_id,image_selector="#vsb_content img.img_vsb_content",instruction="逐字识别图片中明确列出的现任学校领导职务标题与姓名名单，严格保持图片版面顺序；一个职务标题对应多人时，为每个人返回相同职务。名单因版面宽度换行时，即使续行没有重复职务标题，也必须把续行中的全部姓名归入上一职务，直到出现下一个职务标题或图片结束，不得漏掉任何续行姓名。",fetch_mode="raw_http")
    rule["extract_mode"]="vision_grouped_title_names";rule["parser"]="DEEPSEEK_V4_FLASH_VISION_GROUPED_NAMES_V1";rule["risk_flag"]="DeepSeek视觉结果按职务标题行动态解析并合并重复姓名"
    rule["vision_strategy"]["allow_group_title_context"]=True
    rule["vision_strategy"]["tile_edge"]=1600
    return rule

def parse_page(html:str,final_url:str,page_rule:dict)->list:
    """使用 DeepSeek 直接识别图片并完成分组职务证据校验。"""
    from crawler_core.settings import get_settings
    from crawler_core.vision_llm import parse_vision_llm_records

    return parse_vision_llm_records(page_rule,html,final_url,max(get_settings().browser_timeout_seconds,180))

def main(rule_id:str)->None:
    """运行当前页面级在线爬虫。"""
    project_dir=resolve_project_dir()
    if str(project_dir) not in sys.path:sys.path.insert(0,str(project_dir))
    from crawler_core.runner import run_page_adapter
    runtime_context={};page_rule=build_page_rule(rule_id)
    output_path=run_page_adapter(page_rule,globals(),runtime_context=runtime_context,update_fetch_memory=False)
    print(f"实际采集器：{runtime_context.get('actual_collector','')}");print(f"输出文件：{output_path}")

if __name__=="__main__":
    rule_id_value="3612"
    main(rule_id_value)
