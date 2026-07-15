from __future__ import annotations

from datetime import date

from .models import Candidate


TOPIC_ZH = {
    "AI": "人工智能",
    "GIS": "地理信息系统",
    "agriculture": "农业",
    "archaeology": "考古学",
    "architecture": "建筑学",
    "artificial intelligence": "人工智能",
    "atmospheric science": "大气科学",
    "chemistry": "化学",
    "climate": "气候",
    "climate change": "气候变化",
    "climate extremes": "极端气候",
    "climate modelling": "气候建模",
    "computational linguistics": "计算语言学",
    "computational neuroscience": "计算神经科学",
    "computer vision": "计算机视觉",
    "condensed matter": "凝聚态物理",
    "corpus linguistics": "语料库语言学",
    "cosmology": "宇宙学",
    "cryosphere": "冰冻圈",
    "cybersecurity": "网络安全",
    "data analysis": "数据分析",
    "data analytics": "数据分析",
    "data science": "数据科学",
    "databases": "数据库",
    "deep learning": "深度学习",
    "design": "设计",
    "digital humanities": "数字人文",
    "disaster risk": "灾害风险",
    "drought": "干旱",
    "earth observation": "地球观测",
    "ecology": "生态学",
    "economics": "经济学",
    "education research": "教育研究",
    "engineering": "工程学",
    "environmental modelling": "环境建模",
    "environmental science": "环境科学",
    "flood": "洪水",
    "formal methods": "形式化方法",
    "geodesy": "大地测量学",
    "geology": "地质学",
    "geophysics": "地球物理学",
    "geoscience": "地球科学",
    "geospatial": "地理空间",
    "glaciology": "冰川学",
    "groundwater": "地下水",
    "history": "历史学",
    "hydrogeology": "水文地质学",
    "hydrology": "水文学",
    "hydrometeorology": "水文气象学",
    "image processing": "图像处理",
    "international law": "国际法",
    "language documentation": "语言记录",
    "language technology": "语言技术",
    "law": "法学",
    "linguistics": "语言学",
    "literature": "文学",
    "machine learning": "机器学习",
    "mathematics": "数学",
    "mechanics": "力学",
    "meteorology": "气象学",
    "morphology": "形态学",
    "natural hazards": "自然灾害",
    "natural language processing": "自然语言处理",
    "network security": "网络安全",
    "neural computation": "神经计算",
    "neuroAI": "神经人工智能",
    "neuroscience": "神经科学",
    "oceanography": "海洋学",
    "particle physics": "粒子物理",
    "phonetics": "语音学",
    "phonology": "音系学",
    "physics": "物理学",
    "political science": "政治学",
    "probability": "概率论",
    "programming languages": "程序设计语言",
    "psycholinguistics": "心理语言学",
    "remote sensing": "遥感",
    "robotics": "机器人学",
    "satellite": "卫星遥感",
    "scientific machine learning": "科学机器学习",
    "seismology": "地震学",
    "semantics": "语义学",
    "social science": "社会科学",
    "software engineering": "软件工程",
    "soil science": "土壤科学",
    "speech processing": "语音处理",
    "statistical physics": "统计物理",
    "statistics": "统计学",
    "sustainability": "可持续发展",
    "syntax": "句法学",
    "uncertainty quantification": "不确定性量化",
    "water management": "水资源管理",
    "water quality": "水质",
    "water resources": "水资源",
}

MODE_ZH = {
    "in-person": "线下",
    "hybrid": "混合形式",
    "online": "线上",
    "uncertain": "形式待确认",
}

FUNDING_TYPE_ZH = {
    "bursary": "助学金",
    "fee waiver": "费用减免",
    "financial support": "经济资助",
    "funding": "资助",
    "scholarship": "奖学金",
    "stipend": "津贴",
    "travel grant": "差旅资助",
}

STATUS_ZH = {
    "Fully qualified": "完全符合",
    "High quality": "高质量",
    "Found": "已收录",
    "Listed": "已收录",
    "Curated": "人工精选",
}

REGION_ZH = {
    "Africa": "非洲",
    "East Asia": "东亚",
    "Latin America": "拉丁美洲",
    "North America": "北美",
    "South Asia": "南亚",
    "Southeast Asia": "东南亚",
    "UK": "英国",
    "continental Europe": "欧洲大陆",
    "global": "全球",
}

SOURCE_TYPE_ZH = {
    "agency": "机构",
    "aggregator": "聚合平台",
    "community_index": "社区索引",
    "funding_body": "资助机构",
    "intergovernmental_research": "政府间研究机构",
    "research_centre": "研究中心",
    "research_consortium": "研究联盟",
    "research_infrastructure": "科研基础设施",
    "research_institute": "研究所",
    "research_network": "研究网络",
    "scientific_society": "科学学会",
    "summer_school": "暑期学校",
    "university": "大学",
    "university_institute": "大学研究机构",
}


def topics_label_zh(keywords: list[str], limit: int = 4) -> str:
    return "、".join(TOPIC_ZH.get(topic, topic) for topic in keywords[:limit])


def topic_zh(topic: str) -> str:
    return TOPIC_ZH.get(topic, topic)


def mode_zh(mode: str) -> str:
    return MODE_ZH.get(mode, mode or "形式待确认")


def status_zh(status: str) -> str:
    return STATUS_ZH.get(status, status)


def region_zh(region: str) -> str:
    return REGION_ZH.get(region, region)


def source_type_zh(source_type: str) -> str:
    return SOURCE_TYPE_ZH.get(source_type, source_type.replace("_", " "))


def date_zh(value: date | None, *, uncertain: str = "日期待确认") -> str:
    if value is None:
        return uncertain
    return f"{value.year}年{value.month}月{value.day}日"


def duration_zh(candidate: Candidate) -> str:
    start, end, days = candidate.start_date, candidate.end_date, candidate.duration_days
    if start and end:
        date_range = f"{start.year}年{start.month}月{start.day}日–{end.year}年{end.month}月{end.day}日"
        return f"{date_range} · {days}天" if days else date_range
    if start:
        return f"{date_zh(start)}开始" + (f" · {days}天" if days else "")
    if days:
        return f"{days}天"
    return "时长待确认"


def financial_summary_zh(candidate: Candidate) -> str:
    if candidate.funding_available is True:
        funding = "、".join(FUNDING_TYPE_ZH.get(item, item) for item in candidate.funding_type) or "提供资助"
        return f"{funding} · 金额未说明"
    if candidate.fee_eur is not None:
        return f"费用约 EUR {candidate.fee_eur:.0f}"
    return "资助或费用未说明"
