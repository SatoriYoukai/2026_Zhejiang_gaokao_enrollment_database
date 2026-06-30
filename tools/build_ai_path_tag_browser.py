#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a static tag/score browser for the AI-path candidate pool."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTO_POOL = ROOT / "outputs/ai_path_candidates/math_first_compressed_pool_after_rescue_20260629/math_first_after_rescue_auto_pool.csv"
ACCEPTED_AUTO_POOL = ROOT / "outputs/ai_path_candidates/math_first_compressed_pool_after_rescue_20260629/math_first_after_rescue_auto_pool_user_accepted_20260629.csv"
AUTO_POOL = ACCEPTED_AUTO_POOL if ACCEPTED_AUTO_POOL.exists() else DEFAULT_AUTO_POOL
DEFAULT_MANUAL_POOL = ROOT / "outputs/ai_path_candidates/math_first_compressed_pool_after_rescue_20260629/math_first_after_rescue_manual_review.csv"
MANUAL_POOL_USER_PRUNED = ROOT / "outputs/ai_path_candidates/math_first_compressed_pool_after_rescue_20260629/math_first_after_rescue_manual_review_user_pruned_20260629.csv"
MANUAL_POOL = None if ACCEPTED_AUTO_POOL.exists() else (MANUAL_POOL_USER_PRUNED if MANUAL_POOL_USER_PRUNED.exists() else DEFAULT_MANUAL_POOL)
STRENGTH_TAGS = ROOT / "outputs/ai_path_candidates/rank_29k_50k_strength_tags_20260629/rank_29k_50k_strength_tags_merged.csv"
EVIDENCE_FULL_RESULTS = ROOT / "outputs/ai_path_candidates/evidence_supplement_20260629/full_results"
HARD_GAP_RESCUE_RESULTS = ROOT / "outputs/ai_path_candidates/evidence_supplement_20260629/hard_gap_rescue_20260629/results"
WEAK_GAP_RESCUE_RESULTS = ROOT / "outputs/ai_path_candidates/evidence_supplement_20260629/weak_gap_rescue_20260629/results"
MASTER_TABLE = ROOT / "outputs/clean_database/volunteer_master_2026_with_history.csv"
OUT = ROOT / "outputs/ai_path_tag_browser"


ADMISSION_SECTIONS = [
    (
        "2026招生计划",
        [
            "volunteer_id",
            "college_code",
            "college_name",
            "college_key",
            "major_code",
            "major_name",
            "major_key",
            "major_base_key",
            "duration",
            "province",
            "city",
            "degree_level",
            "plan_count",
            "subject_requirement",
            "subject_key",
            "tuition",
            "tuition_raw",
            "remark",
            "source_file",
        ],
    ),
    (
        "2025录取",
        [
            "2025_match_level",
            "2025_history_major_name",
            "2025_history_subject",
            "2025_history_admitted_count",
            "2025_history_avg_score",
            "2025_history_lowest_score",
            "2025_history_lowest_rank",
            "2025_history_lowest_segment",
            "2025_history_source_page",
        ],
    ),
    (
        "2024录取",
        [
            "2024_match_level",
            "2024_history_major_name",
            "2024_history_subject",
            "2024_history_admitted_count",
            "2024_history_avg_score",
            "2024_history_lowest_score",
            "2024_history_lowest_rank",
            "2024_history_lowest_segment",
            "2024_history_source_page",
        ],
    ),
    (
        "2023录取",
        [
            "2023_match_level",
            "2023_history_major_name",
            "2023_history_subject",
            "2023_history_admitted_count",
            "2023_history_avg_score",
            "2023_history_lowest_score",
            "2023_history_lowest_rank",
            "2023_history_lowest_segment",
            "2023_history_source_page",
        ],
    ),
    (
        "历史汇总",
        [
            "history_years_matched",
            "history_ranks",
            "history_latest_rank",
            "history_latest_score",
            "history_avg_rank",
            "history_best_rank",
            "history_easiest_rank",
        ],
    ),
]

ADMISSION_FIELD_LABELS = {
    "volunteer_id": "志愿ID",
    "college_code": "院校代码",
    "college_name": "院校名称",
    "college_key": "院校匹配键",
    "major_code": "专业代码",
    "major_name": "专业名称",
    "major_key": "专业匹配键",
    "major_base_key": "专业基础键",
    "duration": "学制",
    "province": "省份",
    "city": "城市",
    "degree_level": "层次",
    "plan_count": "招生人数",
    "subject_requirement": "选科要求",
    "subject_key": "选科键",
    "tuition": "学费",
    "tuition_raw": "原始学费",
    "remark": "备注",
    "source_file": "计划来源文件",
    "history_years_matched": "匹配历史年份数",
    "history_ranks": "历史位次序列",
    "history_latest_rank": "最近历史位次",
    "history_latest_score": "最近历史分数",
    "history_avg_rank": "历史平均位次",
    "history_best_rank": "历史最高位次",
    "history_easiest_rank": "历史最低位次",
}

for year in ("2023", "2024", "2025"):
    ADMISSION_FIELD_LABELS.update(
        {
            f"{year}_match_level": f"{year}匹配层级",
            f"{year}_history_major_name": f"{year}历史专业名",
            f"{year}_history_subject": f"{year}历史选科",
            f"{year}_history_admitted_count": f"{year}录取人数",
            f"{year}_history_avg_score": f"{year}平均分",
            f"{year}_history_lowest_score": f"{year}最低分",
            f"{year}_history_lowest_rank": f"{year}最低位次",
            f"{year}_history_lowest_segment": f"{year}最低分段",
            f"{year}_history_source_page": f"{year}历史来源页",
        }
    )


TAG_META = {
    "math_primary_clean_path": ("数学主线干净", "fit", 9),
    "math_primary_plus_computation": ("数学+计算", "fit", 8),
    "strong_math_core": ("数学核心强", "fit", 7),
    "numerical_computing_core": ("数值计算/科学计算", "fit", 5),
    "cs_systems_theory_path": ("CS 系统/理论路径", "fit", 6),
    "os_arch_algorithms": ("OS/体系结构/算法", "fit", 5),
    "ai_theory_path": ("AI 理论路径", "fit", 4),
    "ml_dl_foundation": ("ML/DL 基础", "fit", 4),
    "double_first_class_university": ("双一流", "platform", 5),
    "project_211_university": ("211工程", "platform", 4),
    "doctoral_platform": ("博士点/博士平台", "platform", 8),
    "postdoctoral_platform": ("博士后平台", "platform", 5),
    "master_platform": ("硕士点/硕士平台", "platform", 5),
    "computer_science_master": ("计科硕士平台", "platform", 5),
    "software_engineering_master": ("软件工程硕士平台", "platform", 3),
    "math_master_doctoral_platform": ("数学硕博平台", "platform", 8),
    "cs_doctoral_platform": ("计科博士平台", "platform", 8),
    "national_first_class_major": ("国家一流专业", "platform", 6),
    "national_first_class_undergraduate_major": ("国家一流本科专业", "platform", 6),
    "provincial_first_class_major": ("省一流专业", "platform", 3),
    "engineering_accreditation": ("工程认证", "platform", 3),
    "engineering_certified": ("工程认证", "platform", 3),
    "discipline_evaluation_A_plus": ("学科评估 A+", "platform", 12),
    "discipline_evaluation_A": ("学科评估 A", "platform", 11),
    "discipline_evaluation_A_minus": ("学科评估 A-", "platform", 10),
    "fourth_round_discipline_evaluation_B_plus": ("学科评估 B+", "platform", 7),
    "discipline_evaluation_B_plus": ("学科评估 B+", "platform", 7),
    "discipline_evaluation_B": ("学科评估 B", "platform", 5),
    "discipline_evaluation_B_minus": ("学科评估 B-", "platform", 3),
    "discipline_evaluation_C_plus": ("学科评估 C+", "platform", 1),
    "discipline_evaluation_C": ("学科评估 C", "platform", 0),
    "discipline_evaluation_C_minus": ("学科评估 C-", "platform", -1),
    "ESI_computer_science_top_1pct": ("ESI 计科前1%", "platform", 5),
    "honors_or_innovation_class": ("拔尖/创新班", "platform", 6),
    "research_training": ("科研训练", "platform", 4),
    "postgraduate_signal": ("升学信号", "platform", 4),
    "low_off_scope_load": ("低偏离负担", "fit", 5),
    "zhejiang_regional_double_first_class_signal": ("浙江区域认可", "region", 4),
    "provincial_key_university": ("省重点/省部共建", "platform", 2),
    "sino_foreign": ("中外合作风险", "red_flag", -7),
    "tuition_risk": ("学费风险", "red_flag", -8),
    "large_category_or_direction_risk": ("大类/方向风险", "red_flag", -7),
    "finance_business_load": ("金融/商业负担", "red_flag", -8),
    "application_or_employment_heavy": ("应用/就业导向重", "red_flag", -6),
    "software_job_training_load": ("软件就业训练负担", "red_flag", -5),
    "robotics_control_lockin": ("机器人/控制绑定", "red_flag", -7),
    "agriculture_medicine_biology_lockin": ("农医生命方向绑定", "red_flag", -8),
    "energy_power_transport_lockin": ("能源/交通方向绑定", "red_flag", -7),
    "off_target_industry_direction": ("行业方向偏离", "red_flag", -5),
    "training_plan_missing": ("培养方案缺证", "evidence", -2),
    "evidence_weak": ("证据弱", "evidence", -2),
    "source_mismatch": ("来源错配风险", "evidence", -3),
    "only_major_intro": ("仅专业简介", "evidence", -1),
    "self_study_cs_gap": ("需自学 CS", "gap", -1),
    "self_study_ai_gap": ("需自学 AI", "gap", -1),
    "self_study_systems_gap": ("需自学系统", "gap", -1),
}

PROJECT_211_SCHOOLS = [
    "海南大学",
    "云南大学",
    "辽宁大学",
    "四川农业大学",
    "东北林业大学",
    "广西大学",
    "青海大学",
    "安徽大学",
    "贵州大学",
    "新疆大学",
    "延边大学",
    "东北农业大学",
    "中国石油大学",
]

DISCIPLINE_EVAL_ALIASES = {
    "discipline_eval_a_plus": "discipline_evaluation_A_plus",
    "discipline_eval_a": "discipline_evaluation_A",
    "discipline_eval_a_minus": "discipline_evaluation_A_minus",
    "discipline_eval_b_plus": "discipline_evaluation_B_plus",
    "discipline_eval_b": "discipline_evaluation_B",
    "discipline_eval_b_minus": "discipline_evaluation_B_minus",
    "discipline_eval_c_plus": "discipline_evaluation_C_plus",
    "discipline_eval_c": "discipline_evaluation_C",
    "discipline_eval_c_minus": "discipline_evaluation_C_minus",
    "moe_discipline_eval_a_plus": "discipline_evaluation_A_plus",
    "moe_discipline_eval_a": "discipline_evaluation_A",
    "moe_discipline_eval_a_minus": "discipline_evaluation_A_minus",
    "moe_discipline_eval_b_plus": "discipline_evaluation_B_plus",
    "moe_discipline_eval_b": "discipline_evaluation_B",
    "moe_discipline_eval_b_minus": "discipline_evaluation_B_minus",
    "moe_discipline_eval_c_plus": "discipline_evaluation_C_plus",
    "moe_discipline_eval_c": "discipline_evaluation_C",
    "moe_discipline_eval_c_minus": "discipline_evaluation_C_minus",
    "fourth_round_discipline_evaluation_a_plus": "discipline_evaluation_A_plus",
    "fourth_round_discipline_evaluation_a": "discipline_evaluation_A",
    "fourth_round_discipline_evaluation_a_minus": "discipline_evaluation_A_minus",
    "fourth_round_discipline_evaluation_b_plus": "discipline_evaluation_B_plus",
    "fourth_round_discipline_evaluation_b": "discipline_evaluation_B",
    "fourth_round_discipline_evaluation_b_minus": "discipline_evaluation_B_minus",
    "fourth_round_discipline_evaluation_c_plus": "discipline_evaluation_C_plus",
    "fourth_round_discipline_evaluation_c": "discipline_evaluation_C",
    "fourth_round_discipline_evaluation_c_minus": "discipline_evaluation_C_minus",
}

DISCIPLINE_EVAL_GRADE_TAGS = {
    "A+": "discipline_evaluation_A_plus",
    "A": "discipline_evaluation_A",
    "A-": "discipline_evaluation_A_minus",
    "B+": "discipline_evaluation_B_plus",
    "B": "discipline_evaluation_B",
    "B-": "discipline_evaluation_B_minus",
    "C+": "discipline_evaluation_C_plus",
    "C": "discipline_evaluation_C",
    "C-": "discipline_evaluation_C_minus",
}


def extract_discipline_eval_tags(text: str) -> list[str]:
    if not text or not any(marker in text for marker in ["学科评估", "第四轮", "教育部评估", "discipline_eval", "discipline evaluation"]):
        return []
    tags: list[str] = []
    grade = r"(A\+|A-|B\+|B-|C\+|C-|A|B|C)"
    patterns = [
        re.compile(rf"(?:学科评估|第四轮|教育部评估|discipline[_ ]?evaluation)[^。\n\r,;；]{{0,80}}?(?:为|获评|结果为|评为|等级为|[:：])\s*{grade}\s*(?:档|类|等|级)?", re.I),
        re.compile(rf"(?:学科评估|第四轮|教育部评估|discipline[_ ]?evaluation)[^。\n\r,;；]{{0,80}}?{grade}\s*(?:档|类|等|级)", re.I),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            matched_grade = match.group(1).upper()
            if matched_grade in DISCIPLINE_EVAL_GRADE_TAGS:
                tags.append(DISCIPLINE_EVAL_GRADE_TAGS[matched_grade])
    if "第四轮学科评估材料显示CS为B档" in text:
        tags.append("discipline_evaluation_B")
    return list(dict.fromkeys(tags))


def read_hard_evidence_tags() -> dict[str, list[dict[str, str]]]:
    if not EVIDENCE_FULL_RESULTS.exists():
        return {}
    by_pool: dict[str, list[dict[str, str]]] = {}
    for path in sorted(EVIDENCE_FULL_RESULTS.glob("hard_*_results.csv")):
        for row in read_csv(path):
            text = " ".join(
                row.get(field, "")
                for field in [
                    "platform_evidence_summary",
                    "agent_notes",
                    "remaining_gaps",
                    "major_direction_summary",
                ]
            )
            tags = extract_discipline_eval_tags(text)
            if not tags:
                continue
            for pool_id in split_tags(row.get("pool_ids", "")):
                by_pool.setdefault(pool_id, []).extend(
                    {
                        "tag": tag,
                        "source": path.name,
                        "evidence": row.get("platform_evidence_summary", "") or row.get("agent_notes", ""),
                    }
                    for tag in tags
                )
    return by_pool


def split_url_list(value: str) -> list[str]:
    if not value:
        return []
    normalized = value.replace("\n", "|").replace("\r", "|").replace("；", "|").replace(";", "|")
    return [part.strip() for part in normalized.split("|") if part.strip()]


def compact_join(parts: list[str]) -> str:
    return "；".join(part.strip() for part in parts if part and part.strip())


def add_evidence_item(by_pool: dict[str, list[dict]], pool_ids: str, item: dict) -> None:
    for pool_id in split_tags(pool_ids):
        by_pool.setdefault(pool_id, []).append(item)


def read_evidence_panels_by_pool() -> dict[str, list[dict]]:
    by_pool: dict[str, list[dict]] = {}

    if EVIDENCE_FULL_RESULTS.exists():
        for path in sorted(EVIDENCE_FULL_RESULTS.glob("hard_*_results.csv")):
            for row in read_csv(path):
                add_evidence_item(
                    by_pool,
                    row.get("pool_ids", ""),
                    {
                        "kind": "hard",
                        "title": "硬证据初查",
                        "source_file": path.name,
                        "status": row.get("hard_gap_resolved", ""),
                        "confidence": row.get("evidence_confidence", ""),
                        "training_status": row.get("training_plan_status", ""),
                        "major_names": row.get("major_names", ""),
                        "summary": compact_join(
                            [
                                row.get("major_direction_summary", ""),
                                row.get("platform_evidence_summary", ""),
                            ]
                        ),
                        "risks": row.get("off_scope_or_category_risks", ""),
                        "gaps": row.get("remaining_gaps", ""),
                        "notes": row.get("agent_notes", ""),
                        "source_urls": split_url_list(row.get("corrected_source_urls", "")),
                    },
                )
        for path in sorted(EVIDENCE_FULL_RESULTS.glob("weak_*_results.csv")):
            if "_101_" in path.name:
                continue
            for row in read_csv(path):
                add_evidence_item(
                    by_pool,
                    row.get("pool_ids", ""),
                    {
                        "kind": "weak",
                        "title": "弱证据初查",
                        "source_file": path.name,
                        "status": "collected",
                        "confidence": row.get("evidence_confidence", ""),
                        "training_status": "",
                        "major_names": row.get("major_names", ""),
                        "summary": compact_join(
                            [
                                row.get("postgraduate_evidence", ""),
                                row.get("research_access_evidence", ""),
                                row.get("transfer_category_campus_evidence", ""),
                                row.get("dorm_life_evidence", ""),
                                row.get("freedom_time_tax_evidence", ""),
                                row.get("academic_atmosphere_evidence", ""),
                                row.get("cost_flags", ""),
                            ]
                        ),
                        "risks": row.get("cost_flags", ""),
                        "gaps": row.get("remaining_gaps", ""),
                        "notes": row.get("agent_notes", ""),
                        "source_urls": split_url_list(row.get("source_urls", "")),
                    },
                )
        for path in sorted(EVIDENCE_FULL_RESULTS.glob("weak_*_101_results.csv")):
            for row in read_csv(path):
                add_evidence_item(
                    by_pool,
                    row.get("pool_ids", ""),
                    {
                        "kind": "project101",
                        "title": "101计划证据",
                        "source_file": path.name,
                        "status": row.get("project101_status", ""),
                        "confidence": row.get("evidence_confidence", ""),
                        "training_status": row.get("participation_mode", ""),
                        "major_names": row.get("major_names", ""),
                        "summary": compact_join(
                            [
                                row.get("project101_fields", ""),
                                row.get("participation_mode", ""),
                                row.get("evidence_summary", ""),
                            ]
                        ),
                        "risks": "",
                        "gaps": row.get("remaining_gaps", ""),
                        "notes": row.get("agent_notes", ""),
                        "source_urls": split_url_list(row.get("source_urls", "")),
                    },
                )

    if HARD_GAP_RESCUE_RESULTS.exists():
        for path in sorted(HARD_GAP_RESCUE_RESULTS.glob("hard_gap_rescue_*_results.csv")):
            for row in read_csv(path):
                add_evidence_item(
                    by_pool,
                    row.get("pool_ids", ""),
                    {
                        "kind": "hard_rescue",
                        "title": "硬证据救援",
                        "source_file": path.name,
                        "status": row.get("rescue_status", ""),
                        "confidence": row.get("evidence_confidence", ""),
                        "training_status": row.get("training_plan_status", ""),
                        "major_names": row.get("major_names", ""),
                        "summary": compact_join(
                            [
                                row.get("major_direction_summary", ""),
                                row.get("platform_evidence_summary", ""),
                            ]
                        ),
                        "risks": row.get("off_scope_or_category_risks", ""),
                        "gaps": row.get("remaining_gaps", ""),
                        "notes": row.get("agent_notes", ""),
                        "source_urls": split_url_list(row.get("corrected_source_urls", "")),
                    },
                )

    if WEAK_GAP_RESCUE_RESULTS.exists():
        for path in sorted(WEAK_GAP_RESCUE_RESULTS.glob("weak_gap_rescue_*_results.csv")):
            for row in read_csv(path):
                add_evidence_item(
                    by_pool,
                    row.get("pool_ids", ""),
                    {
                        "kind": "weak_rescue",
                        "title": "弱证据救援",
                        "source_file": path.name,
                        "status": row.get("rescue_status", ""),
                        "confidence": row.get("evidence_confidence", ""),
                        "training_status": "",
                        "major_names": row.get("major_names", ""),
                        "summary": compact_join(
                            [
                                row.get("postgraduate_evidence", ""),
                                row.get("research_access_evidence", ""),
                                row.get("transfer_category_campus_evidence", ""),
                                row.get("dorm_life_evidence", ""),
                                row.get("freedom_time_tax_evidence", ""),
                                row.get("academic_atmosphere_evidence", ""),
                                row.get("cost_flags", ""),
                            ]
                        ),
                        "risks": row.get("cost_flags", ""),
                        "gaps": row.get("remaining_gaps", ""),
                        "notes": row.get("agent_notes", ""),
                        "source_urls": split_url_list(row.get("source_urls", "")),
                    },
                )

    for items in by_pool.values():
        items.sort(key=lambda item: (item["kind"], item.get("source_file", "")))
    return by_pool


SCORE_COMPONENTS = {
    "alignment": {"label": "培养方向对齐", "maxScore": 45},
    "platform": {"label": "学术平台", "maxScore": 25},
    "freedom": {"label": "自学自由度", "maxScore": 15},
    "research": {"label": "升学科研机会", "maxScore": 10},
    "life": {"label": "生活弱证据", "maxScore": 5},
}

SCORE_FACTORS = {
    "math_path_bias": ("数学路径偏心", "alignment", "positive", 7),
    "math_clean_path": ("数学主线干净", "alignment", "positive", 13),
    "math_plus_computation": ("数学+计算", "alignment", "positive", 11),
    "strong_math_core": ("数学核心强", "alignment", "positive", 9),
    "numerical_scientific_computing": ("数值计算/科学计算", "alignment", "positive", 7),
    "cs_systems_theory": ("CS 系统/理论路径", "alignment", "positive", 6),
    "systems_arch_algorithms": ("OS/体系结构/算法", "alignment", "positive", 5),
    "ai_theory_path": ("AI 理论路径", "alignment", "positive", 4),
    "ml_dl_foundation": ("ML/DL 基础", "alignment", "positive", 4),
    "low_off_scope_load": ("低偏离负担", "alignment", "positive", 8),
    "double_first_class": ("双一流", "platform", "positive", 6),
    "project_211": ("211工程", "platform", "positive", 5),
    "provincial_key": ("省重点/省部共建", "platform", "positive", 2),
    "doctoral_platform": ("博士点/博士平台", "platform", "positive", 9),
    "postdoctoral_platform": ("博士后平台", "platform", "positive", 4),
    "master_platform": ("硕士点/硕士平台", "platform", "positive", 4),
    "math_degree_platform": ("数学硕博平台", "platform", "positive", 10),
    "cs_doctoral_platform": ("计科博士平台", "platform", "positive", 8),
    "cs_master_platform": ("计科硕士平台", "platform", "positive", 4),
    "software_master_platform": ("软件工程硕士平台", "platform", "positive", 1),
    "national_first_class_major": ("国家一流专业", "platform", "positive", 5),
    "provincial_first_class_major": ("省一流专业", "platform", "positive", 2),
    "engineering_accreditation": ("工程认证", "platform", "positive", 1),
    "esi_cs_top_1pct": ("ESI 计科前1%", "platform", "positive", 5),
    "discipline_eval_a_plus": ("学科评估 A+", "platform", "positive", 12),
    "discipline_eval_a": ("学科评估 A", "platform", "positive", 11),
    "discipline_eval_a_minus": ("学科评估 A-", "platform", "positive", 10),
    "discipline_eval_b_plus": ("学科评估 B+", "platform", "positive", 7),
    "discipline_eval_b": ("学科评估 B", "platform", "positive", 5),
    "discipline_eval_b_minus": ("学科评估 B-", "platform", "positive", 3),
    "discipline_eval_c_plus": ("学科评估 C+", "platform", "positive", 1),
    "discipline_eval_c_minus": ("学科评估 C-", "platform", "penalty", -1),
    "project101_confirmed": ("101计划明确参与", "platform", "positive", 3),
    "honors_innovation": ("拔尖/创新班", "research", "positive", 5),
    "research_training": ("科研训练", "research", "positive", 5),
    "postgraduate_signal": ("升学信号", "research", "positive", 4),
    "tutor_system": ("导师制/本科导师信号", "research", "positive", 3),
    "controlled_major_category": ("大类风险已可控", "freedom", "positive", 3),
    "low_time_tax_signal": ("低时间税信号", "freedom", "positive", 3),
    "good_dorm_signal": ("住宿正面信号", "life", "positive", 2),
    "sino_foreign_risk": ("中外合作风险", "freedom", "penalty", -8),
    "tuition_risk": ("学费风险", "freedom", "penalty", -10),
    "large_category_risk": ("大类/方向风险", "freedom", "penalty", -12),
    "finance_business_load": ("金融/商业负担", "alignment", "penalty", -14),
    "application_employment_heavy": ("应用/就业导向重", "alignment", "penalty", -9),
    "software_job_training_load": ("软件就业训练负担", "alignment", "penalty", -8),
    "robotics_control_lockin": ("机器人/控制绑定", "alignment", "penalty", -12),
    "agri_med_bio_lockin": ("农医生命方向绑定", "alignment", "penalty", -12),
    "energy_transport_lockin": ("能源/交通方向绑定", "alignment", "penalty", -10),
    "industry_direction_offtarget": ("行业方向偏离", "alignment", "penalty", -8),
    "campus_resource_risk": ("校区资源风险", "freedom", "penalty", -5),
    "time_tax_risk": ("时间税/管理负担风险", "freedom", "penalty", -5),
    "dorm_risk": ("住宿风险", "life", "penalty", -3),
}

LABEL_TO_SCORE_FACTOR = {
    "数学主线干净": ["math_clean_path"],
    "数学+计算": ["math_plus_computation"],
    "数学核心强": ["strong_math_core"],
    "数值计算/科学计算": ["numerical_scientific_computing"],
    "CS 系统/理论路径": ["cs_systems_theory"],
    "OS/体系结构/算法": ["systems_arch_algorithms"],
    "AI 理论路径": ["ai_theory_path"],
    "ML/DL 基础": ["ml_dl_foundation"],
    "低偏离负担": ["low_off_scope_load"],
    "双一流": ["double_first_class"],
    "211工程": ["project_211"],
    "省重点/省部共建": ["provincial_key"],
    "博士点/博士平台": ["doctoral_platform"],
    "博士后平台": ["postdoctoral_platform"],
    "硕士点/硕士平台": ["master_platform"],
    "数学硕博平台": ["math_degree_platform"],
    "计科博士平台": ["cs_doctoral_platform"],
    "计科硕士平台": ["cs_master_platform"],
    "软件工程硕士平台": ["software_master_platform"],
    "国家一流专业": ["national_first_class_major"],
    "国家一流本科专业": ["national_first_class_major"],
    "省一流专业": ["provincial_first_class_major"],
    "工程认证": ["engineering_accreditation"],
    "ESI 计科前1%": ["esi_cs_top_1pct"],
    "学科评估 A+": ["discipline_eval_a_plus"],
    "学科评估 A": ["discipline_eval_a"],
    "学科评估 A-": ["discipline_eval_a_minus"],
    "学科评估 B+": ["discipline_eval_b_plus"],
    "学科评估 B": ["discipline_eval_b"],
    "学科评估 B-": ["discipline_eval_b_minus"],
    "学科评估 C+": ["discipline_eval_c_plus"],
    "学科评估 C-": ["discipline_eval_c_minus"],
    "拔尖/创新班": ["honors_innovation"],
    "科研训练": ["research_training"],
    "升学信号": ["postgraduate_signal"],
    "中外合作风险": ["sino_foreign_risk"],
    "学费风险": ["tuition_risk"],
    "大类/方向风险": ["large_category_risk"],
    "金融/商业负担": ["finance_business_load"],
    "应用/就业导向重": ["application_employment_heavy"],
    "软件就业训练负担": ["software_job_training_load"],
    "机器人/控制绑定": ["robotics_control_lockin"],
    "农医生命方向绑定": ["agri_med_bio_lockin"],
    "能源/交通方向绑定": ["energy_transport_lockin"],
    "行业方向偏离": ["industry_direction_offtarget"],
}

CONFIDENCE_ORDER = {"": 0, "low": 1, "derived": 1, "mixed": 2, "medium": 2, "high": 3, "user": 4}
TRAINING_STATUS_ORDER = {"": 0, "not_found": 1, "source_mismatch_fixed": 2, "major_intro_only": 3, "course_grid": 4, "full_plan": 5}
TRAINING_STATUS_CAP = {
    "full_plan": 1.0,
    "course_grid": 0.96,
    "major_intro_only": 0.88,
    "source_mismatch_fixed": 0.74,
    "not_found": 0.65,
    "no_hard_panel": 0.82,
}

MANUAL_DROP_DECISIONS = {
    ("广东工业大学", "计算机类"): "大类分流到计科/软工/网工/信息安全，风险不可控，用户已决定删除。",
    ("广东工业大学", "国际班"): "用户确认广东工业大学计算机相关国际班不用继续研究。",
    ("浙江工商大学", "计算机类"): "分流和培养方向偏应用/商科/软件安全，用户已决定删除。",
}


def score_factor_catalog() -> list[dict]:
    return [
        {
            "key": key,
            "label": label,
            "component": component,
            "kind": kind,
            "defaultWeight": weight,
        }
        for key, (label, component, kind, weight) in SCORE_FACTORS.items()
    ]


def score_schema() -> dict:
    return {
        "version": "score_v3",
        "principles": [
            "位次不进入质量分，质量梯队内再按位次排序。",
            "缺少 AI/CS 内容不扣分，超出数学/芯片/体系结构/ML 理论路径的必修负担强扣分。",
            "证据不足不直接当坏，但会限制对应正向加分的可信上限。",
            "弱证据只作为小权重红旗或提示，不作为硬筛依据。",
        ],
        "components": SCORE_COMPONENTS,
        "factor_catalog": score_factor_catalog(),
    }


def best_confidence(values: list[str]) -> str:
    return max((value or "" for value in values), key=lambda value: CONFIDENCE_ORDER.get(value, 0), default="")


def evidence_text(row: dict, panels: list[dict]) -> str:
    chunks = [
        row.get("college_name_u", ""),
        row.get("major_name_u", ""),
        row.get("one_sentence_rationale", ""),
        row.get("final_reason", ""),
        row.get("rescue_evidence_summary", ""),
        row.get("agent_audit_reason", ""),
    ]
    for panel in panels:
        chunks.extend([panel.get("summary", ""), panel.get("risks", ""), panel.get("gaps", ""), panel.get("notes", "")])
    return " ".join(part for part in chunks if part)


def best_hard_panel(panels: list[dict]) -> dict | None:
    hard_panels = [panel for panel in panels if panel.get("kind") in {"hard", "hard_rescue"}]
    if not hard_panels:
        return None
    return max(hard_panels, key=lambda panel: TRAINING_STATUS_ORDER.get(panel.get("training_status", ""), 0))


def evidence_quality(row: dict, panels: list[dict], strength: dict[str, str] | None) -> dict:
    hard = best_hard_panel(panels)
    training_status = hard.get("training_status", "") if hard else "no_hard_panel"
    hard_confidence = hard.get("confidence", "") if hard else ""
    project101_panels = [panel for panel in panels if panel.get("kind") == "project101"]
    weak_panels = [panel for panel in panels if panel.get("kind") in {"weak", "weak_rescue"}]
    weak_confidence = best_confidence([panel.get("confidence", "") for panel in weak_panels])

    gaps: list[str] = []
    if training_status not in {"full_plan", "course_grid"}:
        gaps.append("缺完整培养方案或课程表")
    if not project101_panels or project101_panels[0].get("status", "") in {"unclear", "no_evidence", ""}:
        gaps.append("101计划参与方式未确认")
    if not weak_panels:
        gaps.append("缺弱证据")
    elif weak_confidence in {"", "low", "mixed"}:
        gaps.append("弱证据置信度不足")
    if strength is None:
        gaps.append("强平台标签来自派生或未补齐")
    if "大类" in row.get("major_name_u", "") or row.get("major_name_u", "").endswith("类"):
        gaps.append("大类分流/方向规则需复核")

    return {
        "training_status": training_status,
        "training_label": {
            "full_plan": "完整培养方案",
            "course_grid": "课程表",
            "major_intro_only": "仅专业简介",
            "source_mismatch_fixed": "来源错配已修正",
            "not_found": "未找到培养方案",
            "no_hard_panel": "无硬证据面板",
        }.get(training_status, training_status or "未知"),
        "alignment_positive_cap": TRAINING_STATUS_CAP.get(training_status, 0.82),
        "hard_confidence": hard_confidence,
        "weak_confidence": weak_confidence,
        "project101_status": project101_panels[0].get("status", "") if project101_panels else "",
        "gaps": list(dict.fromkeys(gaps)),
    }


def add_score_factor(factors: dict[str, dict], key: str, confidence: str, evidence: str = "", source: str = "") -> None:
    meta = SCORE_FACTORS.get(key)
    if not meta:
        return
    label, component, kind, default_weight = meta
    existing = factors.get(key)
    if existing:
        if CONFIDENCE_ORDER.get(confidence or "", 0) > CONFIDENCE_ORDER.get(existing["confidence"], 0):
            existing["confidence"] = confidence or existing["confidence"]
        if evidence and evidence not in existing["evidence"]:
            existing["evidence"].append(evidence)
        if source:
            existing["sources"].add(source)
        return
    factors[key] = {
        "key": key,
        "label": label,
        "component": component,
        "kind": kind,
        "defaultWeight": default_weight,
        "confidence": confidence or "medium",
        "evidence": [evidence] if evidence else [],
        "sources": {source} if source else set(),
    }


NEGATION_PREFIXES = ["未见", "未发现", "未检索到", "未看到", "未能确认", "没有", "无", "不含", "非", "暂无", "未找到", "没找到"]


def contains_unnegated(text: str, tokens: list[str]) -> bool:
    for token in tokens:
        start = 0
        while True:
            index = text.find(token, start)
            if index < 0:
                break
            sentence_start = max(text.rfind(mark, 0, index) for mark in ["。", "；", ";", "\n", "\r"])
            prefix = text[max(sentence_start + 1, index - 40) : index]
            suffix = text[index : index + len(token) + 8]
            if not any(marker in prefix for marker in NEGATION_PREFIXES) and "不足" not in suffix and "较少" not in suffix:
                return True
            start = index + len(token)
    return False


def contains_asserted_time_tax(text: str) -> bool:
    direct_phrases = ["强制晚自习", "强制早操", "强制查寝", "强制打卡", "强制跑操", "早打卡", "晚归登记", "就寝时间", "日常管理较细", "时间税信号", "高时间税"]
    if contains_unnegated(text, direct_phrases):
        return True
    tokens = ["早操", "晚自习", "早晚自习", "查寝"]
    markers = ["开展", "要求", "规定", "必须"]
    for token in tokens:
        start = 0
        while True:
            index = text.find(token, start)
            if index < 0:
                break
            sentence_start = max(text.rfind(mark, 0, index) for mark in ["。", "；", ";", "\n", "\r"])
            sentence_end_candidates = [text.find(mark, index) for mark in ["。", "；", ";", "\n", "\r"]]
            sentence_end_candidates = [value for value in sentence_end_candidates if value >= 0]
            sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(text)
            sentence = text[sentence_start + 1 : sentence_end]
            prefix = sentence[: max(0, index - sentence_start - 1)]
            near_prefix = sentence[max(0, index - sentence_start - 50) : max(0, index - sentence_start - 1)]
            if not any(marker in prefix for marker in NEGATION_PREFIXES) and any(marker in near_prefix for marker in markers):
                return True
            start = index + len(token)
    return False


def derive_score_factors(row: dict[str, str], tags: list[dict], panels: list[dict], strength: dict[str, str] | None) -> list[dict]:
    factors: dict[str, dict] = {}
    text = evidence_text(row, panels)
    major = row.get("major_name_u", "")
    risk_text = " ".join(
        [
            major,
            row.get("one_sentence_rationale", ""),
            row.get("final_reason", ""),
            *(panel.get("risks", "") for panel in panels),
        ]
    )

    if row.get("major_group_code") == "math_stat_info" or any(token in major for token in ["数学", "信息与计算科学", "统计"]):
        add_score_factor(factors, "math_path_bias", "high", "数学/统计/信计路径符合数学优先策略。", "major_group")

    for tag in tags:
        for key in LABEL_TO_SCORE_FACTOR.get(tag.get("label", ""), []):
            add_score_factor(
                factors,
                key,
                tag.get("confidence", "medium"),
                "；".join(tag.get("evidence", [])[:2]),
                ",".join(tag.get("sources", [])),
            )

    for panel in panels:
        if panel.get("kind") == "project101" and panel.get("status") == "confirmed_participant":
            add_score_factor(factors, "project101_confirmed", panel.get("confidence", "medium"), panel.get("summary", ""), panel.get("source_file", ""))

    if any(token in text for token in ["本科导师", "导师制"]):
        add_score_factor(factors, "tutor_system", "medium", "证据中出现本科导师或导师制信号。", "evidence_text")
    if contains_unnegated(text, ["上床下桌", "四人间", "四人寝", "独立卫浴", "独卫", "空调"]):
        add_score_factor(factors, "good_dorm_signal", "medium", "弱证据中出现住宿正面信号。", "weak_evidence")
    if contains_unnegated(text, ["自由", "自主", "选课空间", "宽松"]) and not any(token in text for token in ["不自由", "不宽松", "自由度不足"]):
        add_score_factor(factors, "low_time_tax_signal", "low", "弱证据中出现自由度正面信号。", "weak_evidence")
    if contains_asserted_time_tax(text):
        add_score_factor(factors, "time_tax_risk", "medium", "弱证据中出现时间税或管理负担风险。", "weak_evidence")
    if contains_unnegated(text, ["宿舍紧张", "六人间", "八人间", "无独卫", "无空调"]):
        add_score_factor(factors, "dorm_risk", "medium", "弱证据中出现住宿风险。", "weak_evidence")

    if contains_unnegated(text, ["金融", "证券", "期货", "投资", "保险", "经济预测", "金融量化"]):
        add_score_factor(factors, "finance_business_load", "high", "培养方向或课程证据中出现金融/证券/投资/经济应用负担。", "evidence_text")
    if contains_unnegated(risk_text, ["机器人", "自动化", "控制工程", "控制理论"]):
        add_score_factor(factors, "robotics_control_lockin", "medium", "证据中出现机器人/控制绑定风险。", "evidence_text")
    if contains_unnegated(risk_text, ["制造", "车辆", "建造", "土木", "矿业", "冶金", "石油", "海洋渔业"]):
        add_score_factor(factors, "industry_direction_offtarget", "medium", "证据中出现行业方向绑定。", "evidence_text")
    if contains_unnegated(risk_text, ["生物", "医学", "农业", "农学", "林学"]):
        add_score_factor(factors, "agri_med_bio_lockin", "medium", "证据中出现农医生命方向绑定。", "evidence_text")
    if "中外合作" in major or "中澳" in major:
        add_score_factor(factors, "sino_foreign_risk", "high", "专业名称显示中外合作或中澳项目。", "major_name")

    for value in factors.values():
        value["sources"] = sorted(value["sources"])
        value["evidence"] = value["evidence"][:3]
    return sorted(factors.values(), key=lambda item: (item["component"], item["kind"], item["label"]))


def should_skip_row(row: dict[str, str]) -> str:
    college = row.get("college_name_u", "")
    major = row.get("major_name_u", "")
    for (drop_college, drop_major), reason in MANUAL_DROP_DECISIONS.items():
        if drop_college in college and drop_major in major:
            return reason
    if "中外合作" in major or "中澳" in major:
        if "杭州电子科技大学" in college and "计算机科学与技术" in major:
            return ""
        return "用户改为本人独立填报后，决定中外合作除杭电计算机中外外全部切除。"
    return ""


DEFAULT_PROFILES = {
    "math_first_default": {
        "label": "数学优先默认",
        "description": "数学路径偏心，缺 AI/CS 不扣分，金融/软件就业训练/行业绑定等多余负担强扣分。",
        "componentWeights": {
            "alignment": 45,
            "platform": 25,
            "freedom": 15,
            "research": 10,
            "life": 5,
        },
        "factorWeights": {
            "math_path_bias": 8,
            "math_clean_path": 14,
            "math_plus_computation": 12,
            "strong_math_core": 10,
            "numerical_scientific_computing": 8,
            "cs_systems_theory": 5,
            "systems_arch_algorithms": 4,
            "ai_theory_path": 3,
            "ml_dl_foundation": 3,
            "low_off_scope_load": 9,
            "doctoral_platform": 8,
            "math_degree_platform": 10,
            "cs_doctoral_platform": 6,
            "master_platform": 4,
            "national_first_class_major": 5,
            "discipline_eval_b_plus": 6,
            "honors_innovation": 6,
            "research_training": 5,
            "postgraduate_signal": 4,
            "finance_business_load": -14,
            "software_job_training_load": -9,
            "application_employment_heavy": -8,
            "large_category_risk": -11,
            "robotics_control_lockin": -12,
            "agri_med_bio_lockin": -12,
            "energy_transport_lockin": -10,
            "industry_direction_offtarget": -8,
            "sino_foreign_risk": -8,
            "tuition_risk": -10,
            "time_tax_risk": -5,
            "dorm_risk": -3,
        },
        "tagWeights": {
            "数学主线干净": 12,
            "数学+计算": 10,
            "数学核心强": 8,
            "数值计算/科学计算": 6,
            "CS 系统/理论路径": 5,
            "OS/体系结构/算法": 4,
            "AI 理论路径": 3,
            "ML/DL 基础": 3,
            "低偏离负担": 6,
            "博士点/博士平台": 8,
            "硕士点/硕士平台": 4,
            "数学硕博平台": 9,
            "计科博士平台": 7,
            "国家一流专业": 5,
            "学科评估 B+": 6,
            "拔尖/创新班": 7,
            "科研训练": 5,
            "升学信号": 4,
            "中外合作风险": -8,
            "学费风险": -10,
            "大类/方向风险": -9,
            "金融/商业负担": -10,
            "应用/就业导向重": -7,
            "软件就业训练负担": -6,
            "机器人/控制绑定": -8,
            "农医生命方向绑定": -9,
            "能源/交通方向绑定": -8,
            "行业方向偏离": -6,
            "证据弱": -3,
            "培养方案缺证": -2,
            "来源错配风险": -4,
        },
    },
    "hat_priority": {
        "label": "帽子优先",
        "description": "双一流、211、博士点、学科评估、一流专业权重更高，但仍保留专业偏离强扣分。",
        "componentWeights": {
            "alignment": 35,
            "platform": 38,
            "freedom": 10,
            "research": 12,
            "life": 5,
        },
        "factorWeights": {
            "double_first_class": 12,
            "project_211": 10,
            "doctoral_platform": 12,
            "math_degree_platform": 13,
            "cs_doctoral_platform": 11,
            "master_platform": 5,
            "national_first_class_major": 8,
            "discipline_eval_a_plus": 14,
            "discipline_eval_a": 13,
            "discipline_eval_a_minus": 12,
            "discipline_eval_b_plus": 10,
            "discipline_eval_b": 7,
            "project101_confirmed": 5,
            "math_path_bias": 5,
            "math_clean_path": 9,
            "math_plus_computation": 8,
            "low_off_scope_load": 6,
            "research_training": 6,
            "postgraduate_signal": 5,
            "finance_business_load": -11,
            "software_job_training_load": -7,
            "application_employment_heavy": -6,
            "large_category_risk": -8,
            "robotics_control_lockin": -9,
            "sino_foreign_risk": -7,
            "tuition_risk": -9,
        },
        "tagWeights": {
            "双一流": 12,
            "博士点/博士平台": 12,
            "数学硕博平台": 12,
            "计科博士平台": 11,
            "学科评估 B+": 10,
            "国家一流专业": 8,
            "省重点/省部共建": 4,
            "拔尖/创新班": 5,
            "数学主线干净": 8,
            "数学+计算": 7,
            "CS 系统/理论路径": 5,
            "中外合作风险": -7,
            "学费风险": -9,
            "大类/方向风险": -7,
            "金融/商业负担": -8,
            "应用/就业导向重": -5,
        },
    },
    "region_priority": {
        "label": "地区优先",
        "description": "江浙沪和发达地区加分，同时保留专业红旗扣分。",
        "componentWeights": {
            "alignment": 40,
            "platform": 20,
            "freedom": 18,
            "research": 10,
            "life": 12,
        },
        "factorWeights": {
            "math_path_bias": 7,
            "math_clean_path": 10,
            "math_plus_computation": 9,
            "strong_math_core": 7,
            "cs_systems_theory": 5,
            "low_off_scope_load": 7,
            "doctoral_platform": 5,
            "math_degree_platform": 6,
            "national_first_class_major": 4,
            "research_training": 4,
            "postgraduate_signal": 3,
            "good_dorm_signal": 3,
            "low_time_tax_signal": 4,
            "finance_business_load": -11,
            "software_job_training_load": -8,
            "application_employment_heavy": -7,
            "large_category_risk": -10,
            "robotics_control_lockin": -10,
            "sino_foreign_risk": -7,
            "tuition_risk": -9,
            "time_tax_risk": -6,
            "dorm_risk": -4,
        },
        "regionWeights": {
            "浙江": 8,
            "上海": 7,
            "江苏": 5,
            "广东": 4,
            "北京": 4,
            "天津": 2,
        },
        "tagWeights": {
            "浙江区域认可": 8,
            "数学主线干净": 8,
            "数学+计算": 7,
            "低偏离负担": 5,
            "博士点/博士平台": 5,
            "国家一流专业": 4,
            "中外合作风险": -7,
            "学费风险": -9,
            "大类/方向风险": -8,
            "金融/商业负担": -8,
            "应用/就业导向重": -6,
        },
    },
    "low_friction": {
        "label": "低时间税优先",
        "description": "低偏离、低大类风险、低中外成本、低应用训练负担优先。",
        "componentWeights": {
            "alignment": 45,
            "platform": 15,
            "freedom": 25,
            "research": 10,
            "life": 5,
        },
        "factorWeights": {
            "low_off_scope_load": 14,
            "math_path_bias": 8,
            "math_clean_path": 12,
            "math_plus_computation": 10,
            "strong_math_core": 8,
            "controlled_major_category": 5,
            "low_time_tax_signal": 5,
            "research_training": 5,
            "postgraduate_signal": 4,
            "honors_innovation": 5,
            "doctoral_platform": 5,
            "math_degree_platform": 6,
            "finance_business_load": -14,
            "software_job_training_load": -12,
            "application_employment_heavy": -11,
            "large_category_risk": -14,
            "robotics_control_lockin": -13,
            "agri_med_bio_lockin": -13,
            "energy_transport_lockin": -12,
            "industry_direction_offtarget": -10,
            "sino_foreign_risk": -12,
            "tuition_risk": -12,
            "time_tax_risk": -8,
            "campus_resource_risk": -8,
            "dorm_risk": -5,
        },
        "tagWeights": {
            "低偏离负担": 12,
            "数学主线干净": 10,
            "数学+计算": 9,
            "数学核心强": 7,
            "拔尖/创新班": 6,
            "科研训练": 5,
            "中外合作风险": -12,
            "学费风险": -12,
            "大类/方向风险": -12,
            "金融/商业负担": -12,
            "应用/就业导向重": -10,
            "软件就业训练负担": -9,
            "机器人/控制绑定": -10,
            "农医生命方向绑定": -11,
            "能源/交通方向绑定": -10,
            "证据弱": -5,
            "培养方案缺证": -4,
            "来源错配风险": -5,
        },
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_optional_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    return read_csv(path)


def read_master_by_volunteer_id() -> tuple[dict[str, dict[str, str]], list[str]]:
    if not MASTER_TABLE.exists():
        return {}, []
    with MASTER_TABLE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = {row.get("volunteer_id", ""): row for row in reader if row.get("volunteer_id", "")}
        return rows, list(reader.fieldnames or [])


def build_admission_info(master_row: dict[str, str] | None, fieldnames: list[str]) -> tuple[list[dict], dict[str, str]]:
    if not master_row:
        return [], {}

    used: set[str] = set()
    sections = []
    for title, columns in ADMISSION_SECTIONS:
        items = []
        for column in columns:
            if column not in master_row:
                continue
            used.add(column)
            items.append(
                {
                    "key": column,
                    "label": ADMISSION_FIELD_LABELS.get(column, column),
                    "value": master_row.get(column, ""),
                }
            )
        if items:
            sections.append({"title": title, "items": items})

    remaining = [column for column in fieldnames if column not in used and column in master_row]
    if remaining:
        sections.append(
            {
                "title": "其他主表字段",
                "items": [
                    {
                        "key": column,
                        "label": ADMISSION_FIELD_LABELS.get(column, column),
                        "value": master_row.get(column, ""),
                    }
                    for column in remaining
                ],
            }
        )

    flat = {column: master_row.get(column, "") for column in fieldnames if column in master_row}
    return sections, flat


def split_tags(value: str) -> list[str]:
    if not value:
        return []
    normalized = value.replace("|", ";").replace(",", ";").replace("，", ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def num(value: str):
    try:
        if value in {"", None}:
            return None
        number = float(str(value).replace(",", ""))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def province_guess(college: str) -> str:
    for token in [
        "浙江",
        "上海",
        "江苏",
        "北京",
        "天津",
        "广东",
        "山东",
        "湖南",
        "湖北",
        "四川",
        "重庆",
        "陕西",
        "山西",
        "辽宁",
        "吉林",
        "黑龙江",
        "内蒙古",
        "新疆",
        "青海",
        "宁夏",
        "西藏",
        "云南",
        "贵州",
        "广西",
        "海南",
        "福建",
        "江西",
        "安徽",
        "河南",
        "河北",
        "甘肃",
    ]:
        if token in college:
            return token
    return ""


def tag_label(raw: str) -> tuple[str, str, int]:
    canonical = DISCIPLINE_EVAL_ALIASES.get(raw.strip().lower(), raw)
    if canonical in TAG_META:
        return TAG_META[canonical]
    cleaned = raw.strip()
    return (cleaned, "custom", 0)


def add_tag(tags: dict[str, dict], raw: str, source: str, confidence: str = "medium", evidence: str = "") -> None:
    if not raw:
        return
    label, kind, default_weight = tag_label(raw)
    existing = tags.get(label)
    if existing:
        existing["raw"].add(raw)
        existing["sources"].add(source)
        if evidence:
            existing["evidence"].append(evidence)
        if existing["confidence"] == "low" and confidence in {"medium", "high"}:
            existing["confidence"] = confidence
        if existing["confidence"] == "medium" and confidence == "high":
            existing["confidence"] = confidence
        return
    tags[label] = {
        "label": label,
        "kind": kind,
        "defaultWeight": default_weight,
        "confidence": confidence,
        "raw": {raw},
        "sources": {source},
        "evidence": [evidence] if evidence else [],
    }


def row_tags(row: dict[str, str], strength: dict[str, str] | None, hard_tags_by_pool: dict[str, list[dict[str, str]]] | None = None) -> list[dict]:
    tags: dict[str, dict] = {}
    for raw in split_tags(row.get("positive_tags", "")):
        add_tag(tags, raw, "alignment", "medium", row.get("one_sentence_rationale", ""))
    for raw in split_tags(row.get("risk_tags", "")):
        add_tag(tags, raw, "alignment_risk", "medium", row.get("one_sentence_rationale", ""))

    if "双一流" in row.get("college_name_u", ""):
        add_tag(tags, "double_first_class_university", "college_name", "high")
    if any(school in row.get("college_name_u", "") for school in PROJECT_211_SCHOOLS):
        add_tag(tags, "project_211_university", "college_name", "high", "院校属于211工程高校或其校区。")
    if "省重点" in row.get("college_name_u", "") or "省市共建" in row.get("college_name_u", ""):
        add_tag(tags, "provincial_key_university", "college_name", "medium")
    if "中外合作" in row.get("major_name_u", "") or "中澳" in row.get("major_name_u", ""):
        add_tag(tags, "sino_foreign", "major_name", "high")

    if strength:
        evidence = strength.get("evidence_summary", "")
        confidence = strength.get("label_confidence", "medium") or "medium"
        for field in [
            "strong_labels",
            "discipline_degree_labels",
            "evaluation_labels",
            "regional_reputation_labels",
            "postgraduate_platform_labels",
            "research_training_labels",
            "red_flags_found",
        ]:
            for raw in split_tags(strength.get(field, "")):
                add_tag(tags, raw, f"strength_{field}", confidence, evidence)
    else:
        for raw in split_tags(row.get("rescue_strong_labels", "")):
            add_tag(tags, raw, "derived_rescue", row.get("rescue_confidence", "") or "medium", row.get("rescue_evidence_summary", ""))
        for raw in split_tags(row.get("rescue_substantive_cut_reasons", "")):
            add_tag(tags, raw, "derived_rescue_risk", row.get("rescue_confidence", "") or "medium", row.get("rescue_final_recommendation", ""))
        for raw in split_tags(row.get("agent_platform_signal", "")):
            add_tag(tags, raw, "derived_agent_platform", "low", row.get("agent_audit_reason", ""))
        for raw in split_tags(row.get("agent_discipline_signal", "")):
            add_tag(tags, raw, "derived_agent_discipline", "low", row.get("agent_audit_reason", ""))

    if hard_tags_by_pool:
        for item in hard_tags_by_pool.get(row.get("pool_id", ""), []):
            add_tag(tags, item["tag"], f"hard_evidence_{item['source']}", "medium", item.get("evidence", ""))

    serialized = []
    for tag in tags.values():
        serialized.append(
            {
                "label": tag["label"],
                "kind": tag["kind"],
                "defaultWeight": tag["defaultWeight"],
                "confidence": tag["confidence"],
                "raw": sorted(tag["raw"]),
                "sources": sorted(tag["sources"]),
                "evidence": tag["evidence"][:3],
            }
        )
    serialized.sort(key=lambda item: (item["kind"], item["label"]))
    return serialized


def status_label(status: str) -> str:
    if status.startswith("auto_keep"):
        return "自动保留"
    if status.startswith("manual_review"):
        return "人工复核"
    if status.startswith("drop"):
        return "已切除"
    return status or "未知"


def build_rows() -> list[dict]:
    auto_rows = read_csv(AUTO_POOL)
    manual_rows = read_optional_csv(MANUAL_POOL)
    strength_by_id = {row["pool_id"]: row for row in read_csv(STRENGTH_TAGS)}
    hard_tags_by_pool = read_hard_evidence_tags()
    evidence_by_pool = read_evidence_panels_by_pool()
    master_by_volunteer_id, admission_columns = read_master_by_volunteer_id()

    rows = []
    for source_pool, source_rows in [("auto", auto_rows), ("manual_review", manual_rows)]:
        for row in source_rows:
            skip_reason = should_skip_row(row)
            if skip_reason:
                continue
            volunteer_id = row.get("volunteer_id", "")
            master_row = master_by_volunteer_id.get(volunteer_id)
            admission_info, admission_flat = build_admission_info(master_row, admission_columns)
            strength = strength_by_id.get(row["pool_id"])
            tags = row_tags(row, strength, hard_tags_by_pool)
            rank = num(row.get("predicted_rank", ""))
            province = (master_row or {}).get("province", "") or province_guess(row.get("college_name_u", ""))
            evidence_urls = []
            for field in ["source_urls", "rescue_source_urls", "override_source_url"]:
                evidence_urls.extend(split_tags(row.get(field, "")))
            if strength:
                evidence_urls.extend(strength.get("source_urls", "").replace("|", ";").split(";"))
            evidence_panels = evidence_by_pool.get(row.get("pool_id", ""), [])
            for panel in evidence_panels:
                evidence_urls.extend(panel.get("source_urls", []))
            evidence_urls = [url.strip() for url in evidence_urls if url.strip()]
            quality = evidence_quality(row, evidence_panels, strength)
            score_factors = derive_score_factors(row, tags, evidence_panels, strength)
            rows.append(
                {
                    "pool_id": row.get("pool_id", ""),
                    "volunteer_id": volunteer_id,
                    "college": row.get("college_name_u", ""),
                    "major": row.get("major_name_u", ""),
                    "major_group": row.get("major_group_code", ""),
                    "status": source_pool,
                    "status_label": "自动池" if source_pool == "auto" else status_label(row.get("final_status", "")),
                    "final_status": row.get("final_status", ""),
                    "rank": rank,
                    "rank_certainty": row.get("rank_certainty", ""),
                    "alignment_score": num(row.get("alignment_score", "")),
                    "province": province,
                    "is_deep_safety": row.get("is_deep_safety_exception", "") == "yes",
                    "rationale": row.get("one_sentence_rationale", ""),
                    "final_reason": row.get("final_reason", ""),
                    "strength_confidence": strength.get("label_confidence", "derived") if strength else "derived",
                    "strength_manual_review_needed": strength.get("manual_review_needed", "") if strength else "yes",
                    "strength_evidence_summary": strength.get("evidence_summary", "") if strength else row.get("rescue_evidence_summary", "") or row.get("agent_audit_reason", ""),
                    "tags": tags,
                    "score_v3": {
                        "evidence_quality": quality,
                        "factors": score_factors,
                        "data_gaps": quality["gaps"],
                    },
                    "evidence_urls": list(dict.fromkeys(evidence_urls))[:30],
                    "evidence_panels": evidence_panels,
                    "admission_info": admission_info,
                    "admission_flat": admission_flat,
                }
            )
    rows.sort(key=lambda r: (r["status"] != "auto", r["rank"] or 999999, r["pool_id"]))
    return rows


def pct(count: int, total: int) -> float:
    if not total:
        return 0.0
    return round(count * 100 / total, 1)


def confidence_distribution(values: list[str]) -> dict[str, int]:
    return dict(Counter(value or "missing" for value in values))


def build_data_quality_summary(rows: list[dict]) -> dict:
    total = len(rows)
    factors = Counter()
    factor_confidence: dict[str, list[str]] = {}
    gaps = Counter()
    training = Counter()
    project101 = Counter()
    hard_confidences: list[str] = []
    weak_confidences: list[str] = []

    for row in rows:
        score_v3 = row.get("score_v3", {})
        quality = score_v3.get("evidence_quality", {})
        training[quality.get("training_status", "") or "missing"] += 1
        project101[quality.get("project101_status", "") or "missing"] += 1
        hard_confidences.append(quality.get("hard_confidence", ""))
        weak_confidences.append(quality.get("weak_confidence", ""))
        for gap in score_v3.get("data_gaps", []):
            gaps[gap] += 1
        for factor in score_v3.get("factors", []):
            factors[factor["key"]] += 1
            factor_confidence.setdefault(factor["key"], []).append(factor.get("confidence", ""))

    factor_catalog = {item["key"]: item for item in score_factor_catalog()}
    factor_coverage = []
    for key, count in factors.most_common():
        meta = factor_catalog.get(key, {})
        confidences = factor_confidence.get(key, [])
        high_like = sum(1 for value in confidences if value in {"high", "user"})
        medium_like = sum(1 for value in confidences if value in {"medium", "mixed"})
        factor_coverage.append(
            {
                "key": key,
                "label": meta.get("label", key),
                "component": meta.get("component", ""),
                "kind": meta.get("kind", ""),
                "count": count,
                "coveragePct": pct(count, total),
                "highConfidenceCount": high_like,
                "mediumConfidenceCount": medium_like,
                "confidence": confidence_distribution(confidences),
            }
        )

    full_or_grid = training["full_plan"] + training["course_grid"]
    return {
        "rowCount": total,
        "categories": [
            {
                "key": "hard_filters",
                "label": "硬筛字段",
                "fields": [
                    {"key": "rank", "label": "预测/历史位次", "coverage": total, "coveragePct": 100.0, "confidence": {"database": total}},
                    {"key": "tuition", "label": "学费", "coverage": total, "coveragePct": 100.0, "confidence": {"database": total}},
                    {"key": "plan_count", "label": "招生人数", "coverage": total, "coveragePct": 100.0, "confidence": {"database": total}},
                    {"key": "subject_requirement", "label": "选科要求", "coverage": total, "coveragePct": 100.0, "confidence": {"database": total}},
                ],
            },
            {
                "key": "curriculum_hard_evidence",
                "label": "培养方案硬证据",
                "fields": [
                    {"key": "full_plan_or_course_grid", "label": "完整方案/课程表", "coverage": full_or_grid, "coveragePct": pct(full_or_grid, total), "confidence": dict(training)},
                    {"key": "training_status", "label": "培养证据等级", "coverage": total, "coveragePct": 100.0, "confidence": dict(training)},
                    {"key": "hard_confidence", "label": "硬证据置信", "coverage": sum(1 for value in hard_confidences if value), "coveragePct": pct(sum(1 for value in hard_confidences if value), total), "confidence": confidence_distribution(hard_confidences)},
                ],
            },
            {
                "key": "strong_platform_evidence",
                "label": "强平台证据",
                "fields": [item for item in factor_coverage if item["component"] in {"platform", "research"} and item["kind"] == "positive"],
            },
            {
                "key": "alignment_and_red_flags",
                "label": "对齐与红旗",
                "fields": [item for item in factor_coverage if item["component"] in {"alignment", "freedom"} or item["kind"] == "penalty"],
            },
            {
                "key": "weak_evidence",
                "label": "弱证据",
                "fields": [
                    {"key": "weak_confidence", "label": "弱证据置信", "coverage": sum(1 for value in weak_confidences if value), "coveragePct": pct(sum(1 for value in weak_confidences if value), total), "confidence": confidence_distribution(weak_confidences)},
                    {"key": "project101_status", "label": "101计划状态", "coverage": total, "coveragePct": 100.0, "confidence": dict(project101)},
                    *[item for item in factor_coverage if item["component"] == "life"],
                ],
            },
            {
                "key": "data_gaps",
                "label": "仍需补证据",
                "fields": [
                    {"key": label, "label": label, "coverage": count, "coveragePct": pct(count, total), "confidence": {"gap": count}}
                    for label, count in gaps.most_common()
                ],
            },
        ],
    }


def build_payload(rows: list[dict]) -> dict:
    _, admission_columns = read_master_by_volunteer_id()
    tag_counter = Counter()
    tag_kind = {}
    tag_default_weight = {}
    for row in rows:
        for tag in row["tags"]:
            tag_counter[tag["label"]] += 1
            tag_kind[tag["label"]] = tag["kind"]
            tag_default_weight[tag["label"]] = tag["defaultWeight"]
    tag_catalog = [
        {
            "label": label,
            "count": count,
            "kind": tag_kind.get(label, "custom"),
            "defaultWeight": tag_default_weight.get(label, 0),
        }
        for label, count in tag_counter.most_common()
    ]
    return {
        "generated_from": {
            "auto_pool": str(AUTO_POOL.relative_to(ROOT)).replace("\\", "/"),
            "manual_pool": str(MANUAL_POOL.relative_to(ROOT)).replace("\\", "/") if MANUAL_POOL else None,
            "strength_tags": str(STRENGTH_TAGS.relative_to(ROOT)).replace("\\", "/"),
            "master_table": str(MASTER_TABLE.relative_to(ROOT)).replace("\\", "/"),
        },
        "row_count": len(rows),
        "tagged_29k_50k_rows": sum(1 for row in rows if row["strength_confidence"] != "derived"),
        "derived_tag_rows": sum(1 for row in rows if row["strength_confidence"] == "derived"),
        "admission_columns": admission_columns,
        "tag_catalog": tag_catalog,
        "score_schema": score_schema(),
        "data_quality_summary": build_data_quality_summary(rows),
        "excluded_decisions": [
            {"college": college, "major": major, "reason": reason}
            for (college, major), reason in MANUAL_DROP_DECISIONS.items()
        ],
        "default_profiles": DEFAULT_PROFILES,
        "rows": rows,
    }


def write_static_files(payload: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    (OUT / "data.js").write_text(f"window.AI_PATH_DATA = {data_json};\n", encoding="utf-8")
    (OUT / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    rows = build_rows()
    payload = build_payload(rows)
    write_static_files(payload)
    print(json.dumps({"output": str(OUT), "rows": len(rows), "tagged_29k_50k_rows": payload["tagged_29k_50k_rows"], "derived_tag_rows": payload["derived_tag_rows"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
