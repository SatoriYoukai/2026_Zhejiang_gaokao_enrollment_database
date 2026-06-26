#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a volunteer-plan database from the 2026 plan workbook and 2023-2025 PDFs.

The database grain is one 2026 parallel-volunteer item: college + major.
Historical PDFs do not contain 2026 major codes, so history is matched
conservatively by college code and normalized major name.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import statistics
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from pypdf import PdfReader

from curation_rules import CURATED_AMBIGUOUS_CHOICES, CURATED_REJECTED_MATCHES


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "clean_database"
CACHE_DIR = OUT_DIR / "_cache"
CACHE_VERSION = "curated_final"

PDF_PAGE_RANGES = {
    # 1-based inclusive ordinary-class parallel-admission pages.
    2023: (12, 310),
    2024: (12, 330),
    2025: (12, 349),
}

DIRECT_LOCATIONS = {"北京", "上海", "天津", "重庆", "香港", "澳门"}
PROVINCES = {
    "北京",
    "上海",
    "天津",
    "重庆",
    "河北",
    "山西",
    "内蒙古",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "广西",
    "海南",
    "四川",
    "贵州",
    "云南",
    "西藏",
    "陕西",
    "甘肃",
    "青海",
    "宁夏",
    "新疆",
}

SUBJECT_TERMS = ("不限", "物理", "化学", "生物", "技术", "历史", "地理", "思想政治")
SUBJECT_PATTERN = re.compile(
    r"(不限|(?:物理|化学|生物|技术|历史|地理|思想政治)"
    r"(?:\s*[&/]\s*(?:物理|化学|生物|技术|历史|地理|思想政治))*)$"
)

COLLEGE_ALIASES = {
    # Historical name -> 2026 name. These are treated as the same college identity.
    "嘉兴学院": "嘉兴大学",
    "绍兴文理学院": "绍兴大学",
    "黄冈职业技术学院": "黄冈职业技术大学",
    "湖州师范学院": "湖州师范大学",
    "温州职业技术学院": "温州职业技术大学",
    "金华职业技术学院": "金华职业技术大学",
    "日照职业技术学院": "日照职业技术大学",
    "华北科技学院": "应急管理大学",
    "宁波职业技术学院": "宁波职业技术大学",
    "浙江科技学院": "浙江科技大学",
    "浙江机电职业技术学院": "浙江机电职业技术大学",
    "襄阳职业技术学院": "襄阳职业技术大学",
    "皖南医学院": "皖南医科大学",
    "常州信息职业技术学院": "常州信息职业技术大学",
    "安徽医学高等专科学校": "安徽第二医学院",
    "杭州职业技术学院": "杭州职业技术大学",
    "海南医学院": "海南医科大学",
    "赣南医学院": "赣南医科大学",
    "天津市职业大学": "天津职业大学",
    "吉林化工学院": "吉林化工大学",
    "湖南理工学院": "湖南理工大学",
    "湖北三峡职业技术学院": "湖北三峡职业技术大学",
    "牡丹江医学院": "牡丹江医科大学",
    "合肥学院": "合肥大学",
    "山东商业职业技术学院": "山东商业职业技术大学",
    "昆明冶金高等专科学校": "昆明冶金职业大学",
    "吉林铁道职业技术学院": "吉林铁道职业技术大学",
    "扬州市职业大学": "扬州职业技术大学",
    "苏州职业大学": "苏州职业技术大学",
    "闽江学院": "闽江大学",
    "九江职业技术学院": "江西职业技术大学",
    "潍坊医学院": "山东第二医科大学",
    "滨州学院": "山东航空学院",
    "重庆科技学院": "重庆科技大学",
    "武汉职业技术学院": "武汉职业技术大学",
    "天水师范学院": "天水师范大学",
    "桂林医学院": "桂林医科大学",
    "邢台医学高等专科学校": "邢台医学院",
    "江苏建筑职业技术学院": "江苏建筑职业技术大学",
    "北京社会管理职业学院": "民政职业大学",
    "淮阴工学院": "淮安大学",
    "蚌埠医学院": "蚌埠医科大学",
    "滨州医学院": "山东医药大学",
    "郑州铁路职业技术学院": "郑州铁路职业技术大学",
    "重庆城市管理职业学院": "重庆城市管理职业大学",
    "和田师范专科学校": "新疆和田学院",
    "四川建筑职业技术学院": "四川建筑职业技术大学",
    "四川工程职业技术学院": "四川工程职业技术大学",
    "连云港师范高等专科学校": "连云港师范学院",
    "贵州工业职业技术学院": "贵州工业职业技术大学",
    "新乡医学院": "河南医药大学",
    "天津公安警官职业学院": "天津警察学院",
    "黑龙江农业工程职业学院": "黑龙江农业工程职业技术大学",
    # Confirmed in the curation pass for the user's personal-volunteer database.
    "绍兴文理学院元培学院": "绍兴理工学院",
    "北京工商大学嘉华学院": "北京金融科技学院",
    "大连理工大学城市学院": "大连工程学院",
    "黑龙江建筑职业技术学院": "哈尔滨建筑科技职业大学",
    "常熟理工学院": "苏州工学院",
    "苏州高博软件技术职业学院": "苏州高博职业学院",
    "安徽科技学院": "安徽科技工程大学",
    "安徽商贸职业技术学院": "安徽应用技术职业大学",
    "福州职业技术学院": "福州职业技术大学",
    "江西外语外贸职业学院": "江西外语外贸职业大学",
    "江西中医药高等专科学校": "抚州医药学院",
    "南昌工程学院": "江西水利电力大学",
    "江西泰豪动漫职业学院": "南昌科技职业大学",
    "湖南理工学院南湖学院": "岳阳学院",
    "湖南文理学院芙蓉学院": "常德学院",
    "吉首大学张家界学院": "张家界学院",
    "北京师范大学-香港浸会大学联合国际学院": "北师香港浸会大学",
    "重庆工程职业技术学院": "重庆工程职业技术大学",
    "重庆三峡学院": "重庆三峡科技大学",
    "四川外国语大学成都学院": "成都外国语学院",
    "贵州工商职业学院": "贵州工商职业大学",
    "云南大学滇池学院": "滇池学院",
}


@dataclass
class ParsedLine:
    top: float
    left: str
    subject: str
    admitted_count: int | None
    duration: int | None
    avg_score: int | None
    seg1_score: int | None
    seg1_rank: int | None
    seg2_score: int | None
    seg2_rank: int | None
    raw: str


def normalize_text(value: object) -> str:
    text = "" if value is None or pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("（", "(").replace("）", ")")
    text = text.replace("，", ",").replace("、", ",")
    text = text.replace("﹣", "-").replace("－", "-")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact(value: object) -> str:
    return re.sub(r"\s+", "", normalize_text(value))


def compact_key(value: object, strip_parens: bool = False) -> str:
    text = compact(value)
    text = text.replace("（", "(").replace("）", ")")
    if strip_parens:
        text = re.sub(r"\([^()]*\)", "", text)
    text = re.sub(r"[·,，、\s]", "", text)
    text = text.replace("“", "").replace("”", "").replace('"', "")
    return text


def normalize_subject(value: object) -> str:
    text = compact(value)
    text = text.replace("不提科目要求", "不限")
    text = text.replace("科目考生均须选考方可报考", "")
    text = text.replace("科目考生必须选考方可报考", "")
    text = re.sub(r"\(\d+门\)", "", text)
    text = text.replace(",", "&").replace("/", "|")
    text = text.replace("&&", "&")
    return text


def canonical_college_key(value: object) -> str:
    key = compact_key(value, strip_parens=True)
    return COLLEGE_ALIASES.get(key, key)


def compatible_college_keys(plan_key: object, history_key: object) -> bool:
    plan = canonical_college_key(plan_key)
    hist = canonical_college_key(history_key)
    if not plan or not hist:
        return False
    return plan == hist


def curated_match_key(level: str, college_code: object, major_name: object, history_major_name: object) -> tuple[str, str, str, str]:
    return (
        normalize_text(level),
        code4(college_code),
        normalize_text(major_name),
        normalize_text(history_major_name),
    )


def load_curation_rules() -> tuple[set[tuple[str, str, str, str]], dict[tuple[str, str], str]]:
    """Load compact curation rules used by the public build."""
    rejected = {
        curated_match_key(level, college_code, major_name, history_major_name)
        for level, college_code, major_name, history_major_name in CURATED_REJECTED_MATCHES
    }
    forced_ambiguous = {
        (normalize_text(volunteer_id), str(year)): normalize_text(chosen_history_major)
        for volunteer_id, year, chosen_history_major in CURATED_AMBIGUOUS_CHOICES
        if normalize_text(chosen_history_major)
    }
    return rejected, forced_ambiguous


def apply_college_name_repairs(history: pd.DataFrame) -> pd.DataFrame:
    """Repair known extraction truncations without making broad college aliases."""
    if history.empty:
        return history
    out = history.copy()
    mask = (out["college_code"] == "6517") & (out["college_name"] == "中国石油大学")
    if mask.any():
        repaired_name = "中国石油大学(北京)克拉玛依校区(“双一流”建设高校)"
        out.loc[mask, "college_name"] = repaired_name
        out.loc[mask, "college_key"] = compact_key(repaired_name, strip_parens=True)
    return out


def to_int(value: object) -> int | None:
    if isinstance(value, float):
        if pd.isna(value):
            return None
        if value.is_integer():
            return int(value)
    text = compact(value)
    if not text:
        return None
    if re.fullmatch(r"\d+\.0", text):
        return int(text[:-2])
    text = re.sub(r"[^\d]", "", text)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def code4(value: object) -> str:
    n = to_int(value)
    return f"{n:04d}" if n is not None else ""


def code3(value: object) -> str:
    n = to_int(value)
    return f"{n:03d}" if n is not None else ""


def join_words(words: Iterable[dict]) -> str:
    ordered = sorted(words, key=lambda w: w["x0"])
    return normalize_text("".join(w["text"] for w in ordered))


def group_words_by_line(words: list[dict], tolerance: float = 3.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if word["top"] < 95 or word["top"] > 720:
            continue
        for line in lines:
            if abs(line[0]["top"] - word["top"]) <= tolerance:
                line.append(word)
                break
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w["x0"]) for line in sorted(lines, key=lambda ws: ws[0]["top"])]


def parse_line(words: list[dict]) -> ParsedLine:
    def col(lo: float, hi: float) -> str:
        return join_words(w for w in words if lo <= w["x0"] < hi)

    left = col(55, 250)
    subject = col(250, 305)
    raw = join_words(words)
    return ParsedLine(
        top=words[0]["top"],
        left=left,
        subject=subject,
        admitted_count=to_int(col(305, 334)),
        duration=to_int(col(334, 363)),
        avg_score=to_int(col(363, 386)),
        seg1_score=to_int(col(386, 408)),
        seg1_rank=to_int(col(408, 436)),
        seg2_score=to_int(col(436, 462)),
        seg2_rank=to_int(col(462, 502)),
        raw=raw,
    )


def detect_college(left: str) -> dict | None:
    text = normalize_text(left)
    if not text or text.startswith("[") or "院校代码" in text:
        return None

    matches = list(re.finditer(r"\(([^()]*)\)", text))
    for match in matches:
        body = compact(match.group(1))
        is_location = "·" in body or body in DIRECT_LOCATIONS or body in PROVINCES
        if not is_location:
            continue
        prefix = text[: match.start()].strip()
        code_match = re.match(r"^(\d{4})(.*)$", prefix)
        college_code = code_match.group(1) if code_match else ""
        college_name = code_match.group(2).strip() if code_match else prefix
        college_name = re.sub(r"^[\d\s]+", "", college_name).strip()
        college_name = re.sub(r"\([^()]*$", "", college_name).strip()
        if len(college_name) < 2:
            continue
        return {
            "college_code": college_code,
            "college_name": college_name,
            "location": body,
            "remainder": text[match.end() :].strip(),
        }
    return None


def clean_major(value: str) -> str:
    text = compact(value)
    if not text:
        return ""
    text = re.sub(r"^\d{2}(.{1})\d{2}", r"\1", text)
    text = re.sub(r"^\d{4}", "", text)
    text = re.sub(r"^\[[^\]]+\]", "", text)
    text = text.replace("　", "")
    return normalize_text(text)


def has_data(parsed: ParsedLine) -> bool:
    return (
        parsed.admitted_count is not None
        and parsed.duration is not None
        and parsed.avg_score is not None
        and (parsed.seg1_score is not None or parsed.seg2_score is not None)
    )


def split_tail_numbers(line: str) -> tuple[str, list[int]]:
    tokens = normalize_text(line).replace("\u3000", " ").split()
    numbers: list[int] = []
    while tokens and re.fullmatch(r"\d+", tokens[-1]):
        numbers.append(int(tokens.pop()))
    numbers.reverse()
    return normalize_text(" ".join(tokens)), numbers


def split_subject(prefix: str) -> tuple[str, str]:
    text = normalize_text(prefix).replace("＆", "&")
    text = re.sub(r"\s*&\s*", "&", text)
    text = re.sub(r"\s*/\s*", "/", text)
    match = SUBJECT_PATTERN.search(text)
    if not match:
        return text, ""
    major = normalize_text(text[: match.start()])
    return major, normalize_subject(match.group(1))


def parse_tail_scores(numbers: list[int]) -> dict | None:
    if len(numbers) < 4:
        return None

    admitted_count, duration, avg_score = numbers[0], numbers[1], numbers[2]
    tail = numbers[3:]
    if duration < 1 or duration > 8 or avg_score < 100 or avg_score > 750:
        return None

    seg1_score = seg1_rank = seg2_score = seg2_rank = None
    lowest_segment = ""

    if len(tail) >= 4:
        # Typical shape: count, duration, avg, one_score, one_rank, two_score, two_rank.
        seg1_score, seg1_rank, seg2_score, seg2_rank = tail[:4]
        lowest_score, lowest_rank, lowest_segment = seg2_score, seg2_rank, "二段"
    elif len(tail) == 3 and tail[1] < 750 and tail[2] > 1000:
        # Shape near the section boundary: one_score, two_score, two_rank.
        # The one-segment rank is omitted, so the final admission line is two_score/two_rank.
        seg1_score, seg2_score, seg2_rank = tail
        lowest_score, lowest_rank, lowest_segment = seg2_score, seg2_rank, "二段"
    elif len(tail) >= 2:
        score, rank = tail[0], tail[1]
        if score >= 492:
            seg1_score, seg1_rank, lowest_segment = score, rank, "一段"
        else:
            seg2_score, seg2_rank, lowest_segment = score, rank, "二段"
        lowest_score, lowest_rank = score, rank
    else:
        score = tail[0]
        if score < 492:
            seg2_score, lowest_segment = score, "二段"
        else:
            seg1_score, lowest_segment = score, "一段"
        lowest_score, lowest_rank = score, None

    return {
        "admitted_count": admitted_count,
        "duration": duration,
        "avg_score": avg_score,
        "seg1_score": seg1_score,
        "seg1_rank": seg1_rank,
        "seg2_score": seg2_score,
        "seg2_rank": seg2_rank,
        "lowest_score": lowest_score,
        "lowest_rank": lowest_rank,
        "lowest_segment": lowest_segment,
    }


def final_score_rank(row: dict) -> tuple[int | None, int | None, str]:
    if row.get("seg2_rank") is not None:
        return row.get("seg2_score"), row.get("seg2_rank"), "二段"
    if row.get("seg1_rank") is not None:
        return row.get("seg1_score"), row.get("seg1_rank"), "一段"
    if row.get("seg2_score") is not None:
        return row.get("seg2_score"), None, "二段"
    return row.get("seg1_score"), row.get("seg1_rank"), "一段"


def read_2026_plan() -> pd.DataFrame:
    workbook = next(p for p in ROOT.iterdir() if p.suffix.lower() == ".xlsm")
    df = pd.read_excel(workbook, sheet_name="Sheet1", header=1, engine="openpyxl")
    df = df[df.iloc[:, 1].notna() & df.iloc[:, 3].notna()].copy()
    df.columns = [
        "preselect_order",
        "college_code",
        "college_name",
        "major_code",
        "major_name",
        "duration",
        "province",
        "city",
        "degree_level",
        "plan_count",
        "subject_requirement",
        "tuition",
        "remark",
    ]
    df["college_code"] = df["college_code"].map(code4)
    df["major_code"] = df["major_code"].map(code3)
    df["volunteer_id"] = df["college_code"] + "-" + df["major_code"]
    for col in ["college_name", "major_name", "province", "city", "degree_level", "subject_requirement", "remark"]:
        df[col] = df[col].map(normalize_text)
    for col in ["duration", "plan_count", "tuition"]:
        df[col] = df[col].map(to_int)
    df["college_key"] = df["college_name"].map(lambda x: compact_key(x, strip_parens=True))
    df["major_key"] = df["major_name"].map(lambda x: compact_key(x, strip_parens=False))
    df["major_base_key"] = df["major_name"].map(lambda x: compact_key(x, strip_parens=True))
    df["subject_key"] = df["subject_requirement"].map(normalize_subject)
    df["source_file"] = workbook.name
    cols = [
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
        "remark",
        "source_file",
    ]
    return df[cols].reset_index(drop=True)


def parse_history_pdf(pdf_path: Path, year: int) -> list[dict]:
    start_page, end_page = PDF_PAGE_RANGES[year]
    rows: list[dict] = []
    current = {"college_code": "", "college_name": "", "location": ""}
    pending_name = ""
    pending_subject = ""

    reader = PdfReader(str(pdf_path))
    last_page = min(end_page, len(reader.pages))
    for page_number in range(start_page, last_page + 1):
        if page_number == start_page or page_number % 50 == 0 or page_number == last_page:
            print(f"{year}: reading PDF page {page_number}/{last_page}", flush=True)
        page = reader.pages[page_number - 1]
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = normalize_text(raw_line)
            if not line:
                continue
            if "艺术类" in line or "体育类" in line:
                continue
            if "院校代码" in line or line in {"录", "取", "人", "数", "学", "制", "平均分", "一段", "二段"}:
                continue
            if line.startswith("["):
                continue

            prefix, numbers = split_tail_numbers(line)
            college = detect_college(prefix)
            if college:
                current = {
                    "college_code": college["college_code"] or current.get("college_code", ""),
                    "college_name": college["college_name"],
                    "location": college["location"],
                }
                prefix = college["remainder"]
                pending_name = ""
                pending_subject = ""
                if not prefix and len(numbers) < 4:
                    continue

            scores = parse_tail_scores(numbers)
            if scores:
                major_part, subject = split_subject(prefix)
                major = clean_major(major_part)
                if (not major or major in {"&", "/"}) and pending_name:
                    major = pending_name
                    subject = subject or pending_subject
                elif pending_name and len(major) <= 3:
                    major = pending_name + major
                    subject = subject or pending_subject
                if not subject and major.endswith(SUBJECT_TERMS):
                    major_part, subject = split_subject(major)
                    major = clean_major(major_part)
                if not major or "院校代码" in major:
                    continue
                row = {
                    "year": year,
                    "college_code": current.get("college_code", ""),
                    "college_name": current.get("college_name", ""),
                    "college_key": compact_key(current.get("college_name", ""), strip_parens=True),
                    "location": current.get("location", ""),
                    "major_name": major,
                    "major_key": compact_key(major, strip_parens=False),
                    "major_base_key": compact_key(major, strip_parens=True),
                    "subject": subject,
                    "subject_key": subject,
                    "source_file": pdf_path.name,
                    "source_page": page_number,
                    "raw_line": line,
                }
                row.update(scores)
                rows.append(row)
                pending_name = ""
                pending_subject = ""
                continue

            candidate_part, subject = split_subject(prefix)
            candidate = clean_major(candidate_part)
            if candidate and not detect_college(candidate) and "院校代码" not in candidate:
                pending_name = candidate
                pending_subject = subject

    # Remove exact duplicate extractions caused by wrapped/nearby lines.
    deduped: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row["year"],
            row["college_code"],
            row["college_key"],
            row["major_key"],
            row["source_page"],
            row.get("lowest_score"),
            row.get("lowest_rank"),
        )
        deduped.setdefault(key, row)
    return list(deduped.values())


def build_history() -> pd.DataFrame:
    rows: list[dict] = []
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for year in sorted(PDF_PAGE_RANGES):
        pdf = next(p for p in ROOT.glob(f"{year}*.pdf"))
        cache_path = CACHE_DIR / f"{CACHE_VERSION}_admissions_history_{year}.csv"
        if cache_path.exists() and cache_path.stat().st_mtime >= pdf.stat().st_mtime:
            year_df = pd.read_csv(cache_path, dtype={"college_code": str}).where(pd.notna, None)
            for col in [
                "college_code",
                "college_name",
                "college_key",
                "location",
                "major_name",
                "major_key",
                "major_base_key",
                "subject",
                "subject_key",
                "source_file",
                "raw_line",
            ]:
                if col in year_df.columns:
                    year_df[col] = year_df[col].map(lambda x: "" if x is None else normalize_text(x))
            year_rows = year_df.where(pd.notna(year_df), None).to_dict("records")
            print(f"{year}: loaded {len(year_rows):,} cached rows from {cache_path.name}")
        else:
            year_rows = parse_history_pdf(pdf, year)
            write_csv(cache_path, pd.DataFrame(year_rows))
            print(f"{year}: parsed {len(year_rows):,} ordinary parallel rows from {pdf.name}")
        rows.extend(year_rows)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = apply_college_name_repairs(df)
    df["match_college_key"] = df.apply(
        lambda r: r["college_code"] if r.get("college_code") else r.get("college_key", ""), axis=1
    )
    return df


def fill_history_college_codes(history: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history

    out = history.copy()
    plan_pairs = plan[["college_key", "college_code"]].drop_duplicates()
    unique_counts = plan_pairs.groupby("college_key")["college_code"].nunique()
    unique_keys = set(unique_counts[unique_counts == 1].index)
    code_by_college_key = (
        plan_pairs[plan_pairs["college_key"].isin(unique_keys)]
        .set_index("college_key")["college_code"]
        .to_dict()
    )

    def current_code(value: object) -> str:
        text = normalize_text(value)
        return code4(text) if text else ""

    out["college_code_source"] = out["college_code"].map(lambda x: "pdf" if current_code(x) else "")
    out["college_code"] = out["college_code"].map(current_code)

    fill_mask = out["college_code"] == ""
    filled_codes = out.loc[fill_mask, "college_key"].map(lambda x: code_by_college_key.get(normalize_text(x), ""))
    out.loc[fill_mask, "college_code"] = filled_codes
    out.loc[fill_mask & (out["college_code"] != ""), "college_code_source"] = "plan_college_key"
    out["match_college_key"] = out.apply(
        lambda r: r["college_code"] if r.get("college_code") else r.get("college_key", ""), axis=1
    )
    return out


def unique_history_indexes(history: pd.DataFrame) -> dict[str, dict[tuple, dict]]:
    indexes: dict[str, dict[tuple, dict]] = {}
    if history.empty:
        return indexes

    for level, major_col in [("exact", "major_key"), ("base", "major_base_key")]:
        grouped: dict[tuple, list[dict]] = {}
        for row in history.to_dict("records"):
            college_part = row.get("college_code") or row.get("college_key")
            key = (row["year"], college_part, row.get(major_col, ""))
            grouped.setdefault(key, []).append(row)
        indexes[level] = {key: vals[0] for key, vals in grouped.items() if len(vals) == 1 and key[2]}
    return indexes


def history_by_year_college(history: pd.DataFrame) -> dict[tuple, list[dict]]:
    buckets: dict[tuple, list[dict]] = {}
    if history.empty:
        return buckets
    for row in history.to_dict("records"):
        college_part = row.get("college_code") or row.get("college_key")
        buckets.setdefault((row["year"], college_part), []).append(row)
    return buckets


def match_history(plan: pd.DataFrame, history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    indexes = unique_history_indexes(history)
    history_buckets = history_by_year_college(history)
    rejected_matches, forced_ambiguous = load_curation_rules()
    output = plan.copy()
    audit_rows: list[dict] = []
    identity_rows: list[dict] = []
    rejected_rows: list[dict] = []
    plan_base_counts = output.groupby(["college_code", "major_base_key"]).size().to_dict()

    for year in sorted(PDF_PAGE_RANGES):
        for col in [
            "match_level",
            "history_major_name",
            "history_subject",
            "history_admitted_count",
            "history_avg_score",
            "history_lowest_score",
            "history_lowest_rank",
            "history_lowest_segment",
            "history_source_page",
        ]:
            output[f"{year}_{col}"] = pd.Series([None] * len(output), dtype="object")

    def reject_key(level: str, plan_row: pd.Series, hist_row: dict) -> tuple[str, str, str, str]:
        return curated_match_key(
            level,
            plan_row.get("college_code", ""),
            plan_row.get("major_name", ""),
            hist_row.get("major_name", ""),
        )

    def is_rejected(level: str, plan_row: pd.Series, hist_row: dict) -> bool:
        return reject_key(level, plan_row, hist_row) in rejected_matches

    def record_rejected(level: str, plan_row: pd.Series, year: int, hist_row: dict) -> None:
        if not is_rejected(level, plan_row, hist_row):
            return
        rejected_rows.append(
            {
                "volunteer_id": plan_row.get("volunteer_id", ""),
                "year": year,
                "college_code": plan_row.get("college_code", ""),
                "college_name": plan_row.get("college_name", ""),
                "major_name": plan_row.get("major_name", ""),
                "history_college_name": hist_row.get("college_name", ""),
                "history_major_name": hist_row.get("major_name", ""),
                "history_lowest_score": hist_row.get("lowest_score", ""),
                "history_lowest_rank": hist_row.get("lowest_rank", ""),
                "history_source_page": hist_row.get("source_page", ""),
                "match_level": level,
            }
        )

    for idx, row in output.iterrows():
        for year in sorted(PDF_PAGE_RANGES):
            candidates: list[tuple[str, dict]] = []
            college_keys = []
            for key in [row["college_code"], row["college_key"]]:
                key = normalize_text(key)
                if key and key not in college_keys:
                    college_keys.append(key)
            for level, key_value in [
                ("exact", row["major_key"]),
                ("base", row["major_base_key"]),
            ]:
                if level == "base" and plan_base_counts.get((row["college_code"], row["major_base_key"]), 0) != 1:
                    continue
                for college_key in college_keys:
                    hist = indexes.get(level, {}).get((year, college_key, key_value))
                    if hist and not is_rejected(level, row, hist):
                        candidates.append((level, hist))
                        break
                    if hist:
                        record_rejected(level, row, year, hist)
                if candidates:
                    break

            if not candidates:
                # Conservative contains matching within the same college and year.
                contains = []
                if plan_base_counts.get((row["college_code"], row["major_base_key"]), 0) == 1:
                    same_college = []
                    for college_key in college_keys:
                        same_college.extend(history_buckets.get((year, college_key), []))
                    plan_major_base = normalize_text(row["major_base_key"])
                    contains = [
                        h
                        for h in same_college
                        if normalize_text(h.get("major_base_key"))
                        and (
                            normalize_text(h["major_base_key"]) == plan_major_base
                            or normalize_text(h["major_base_key"]) in plan_major_base
                            or plan_major_base in normalize_text(h["major_base_key"])
                        )
                    ]
                unique_by_major = {(h["major_key"], h.get("lowest_rank")): h for h in contains}
                forced_major = forced_ambiguous.get((row["volunteer_id"], str(year)), "")
                if forced_major:
                    forced = [
                        h for h in contains
                        if normalize_text(h.get("major_name", "")) == forced_major
                    ]
                    row_duration = to_int(row.get("duration"))
                    duration_forced = [
                        h for h in forced
                        if row_duration is not None and to_int(h.get("duration")) == row_duration
                    ]
                    if duration_forced:
                        forced = duration_forced
                    unique_forced = {
                        (
                            h.get("major_key"),
                            h.get("duration"),
                            h.get("lowest_score"),
                            h.get("lowest_rank"),
                            h.get("source_page"),
                        ): h
                        for h in forced
                    }
                    if len(unique_forced) == 1:
                        hist = next(iter(unique_forced.values()))
                        if not is_rejected("manual_ambiguous", row, hist):
                            candidates.append(("manual_ambiguous", hist))
                    elif contains:
                        audit_rows.append(
                            {
                                "volunteer_id": row["volunteer_id"],
                                "year": year,
                                "college_code": row["college_code"],
                                "college_name": row["college_name"],
                                "major_name": row["major_name"],
                                "candidate_count": len(contains),
                                "candidate_majors": "; ".join(sorted({h["major_name"] for h in contains})[:10]),
                                "curated_chosen_major": forced_major,
                                "curated_resolution_status": "not_unique",
                            }
                        )
                elif len(unique_by_major) == 1:
                    hist = next(iter(unique_by_major.values()))
                    if not is_rejected("contains_unique", row, hist):
                        candidates.append(("contains_unique", hist))
                    else:
                        record_rejected("contains_unique", row, year, hist)
                elif contains:
                    audit_rows.append(
                        {
                            "volunteer_id": row["volunteer_id"],
                            "year": year,
                            "college_code": row["college_code"],
                            "college_name": row["college_name"],
                            "major_name": row["major_name"],
                            "candidate_count": len(contains),
                            "candidate_majors": "; ".join(sorted({h["major_name"] for h in contains})[:10]),
                        }
                    )

            if not candidates:
                continue

            level, hist = candidates[0]
            if not compatible_college_keys(row.get("college_key", ""), hist.get("college_key", "")):
                identity_rows.append(
                    {
                        "volunteer_id": row["volunteer_id"],
                        "year": year,
                        "college_code": row["college_code"],
                        "college_name": row["college_name"],
                        "college_key": row.get("college_key", ""),
                        "history_college_name": hist.get("college_name", ""),
                        "history_college_key": hist.get("college_key", ""),
                        "major_name": row["major_name"],
                        "history_major_name": hist.get("major_name", ""),
                        "history_lowest_score": hist.get("lowest_score", ""),
                        "history_lowest_rank": hist.get("lowest_rank", ""),
                        "history_source_page": hist.get("source_page", ""),
                        "match_level": level,
                    }
                )
                continue
            output.at[idx, f"{year}_match_level"] = level
            output.at[idx, f"{year}_history_major_name"] = hist.get("major_name", "")
            output.at[idx, f"{year}_history_subject"] = hist.get("subject", "")
            output.at[idx, f"{year}_history_admitted_count"] = hist.get("admitted_count", "")
            output.at[idx, f"{year}_history_avg_score"] = hist.get("avg_score", "")
            output.at[idx, f"{year}_history_lowest_score"] = hist.get("lowest_score", "")
            output.at[idx, f"{year}_history_lowest_rank"] = hist.get("lowest_rank", "")
            output.at[idx, f"{year}_history_lowest_segment"] = hist.get("lowest_segment", "")
            output.at[idx, f"{year}_history_source_page"] = hist.get("source_page", "")

    return output, pd.DataFrame(audit_rows), pd.DataFrame(identity_rows), pd.DataFrame(rejected_rows)


def add_summary_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rank_cols = [f"{year}_history_lowest_rank" for year in sorted(PDF_PAGE_RANGES)]
    score_cols = [f"{year}_history_lowest_score" for year in sorted(PDF_PAGE_RANGES)]
    match_cols = [f"{year}_match_level" for year in sorted(PDF_PAGE_RANGES)]

    def numeric_values(row: pd.Series, cols: list[str]) -> list[int]:
        vals = []
        for col in cols:
            value = to_int(row.get(col))
            if value is not None:
                vals.append(value)
        return vals

    out["history_years_matched"] = out.apply(
        lambda r: sum(1 for col in match_cols if normalize_text(r.get(col)) != ""),
        axis=1,
    )
    out["history_ranks"] = out.apply(
        lambda r: ";".join(str(v) for v in numeric_values(r, rank_cols)), axis=1
    )
    out["history_latest_rank"] = out.apply(
        lambda r: next((to_int(r.get(col)) for col in reversed(rank_cols) if to_int(r.get(col)) is not None), None),
        axis=1,
    )
    out["history_latest_score"] = out.apply(
        lambda r: next((to_int(r.get(col)) for col in reversed(score_cols) if to_int(r.get(col)) is not None), None),
        axis=1,
    )
    out["history_avg_rank"] = out.apply(
        lambda r: round(statistics.mean(numeric_values(r, rank_cols))) if numeric_values(r, rank_cols) else None,
        axis=1,
    )
    out["history_best_rank"] = out.apply(
        lambda r: min(numeric_values(r, rank_cols)) if numeric_values(r, rank_cols) else None,
        axis=1,
    )
    out["history_easiest_rank"] = out.apply(
        lambda r: max(numeric_values(r, rank_cols)) if numeric_values(r, rank_cols) else None,
        axis=1,
    )
    return out


def write_csv(path: Path, rows: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def write_sqlite(path: Path, tables: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX idx_plan_2026_volunteer_id ON plan_2026(volunteer_id)")
        conn.execute("CREATE INDEX idx_plan_2026_college_major ON plan_2026(college_code, major_code)")
        conn.execute("CREATE INDEX idx_history_year_college_major ON admissions_history(year, college_code, major_key)")
        conn.execute("CREATE INDEX idx_master_latest_rank ON volunteer_master(history_latest_rank)")
        if "college_identity_mismatches" in tables:
            conn.execute(
                "CREATE INDEX idx_identity_mismatch_volunteer_year "
                "ON college_identity_mismatches(volunteer_id, year)"
            )
        if "curated_rejections" in tables:
            conn.execute(
                "CREATE INDEX idx_curated_rejections_volunteer_year "
                "ON curated_rejections(volunteer_id, year)"
            )


def write_excel(path: Path, tables: dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, df in tables.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            for column_name in ["volunteer_id", "college_code", "major_code"]:
                if column_name not in df.columns:
                    continue
                col_idx = df.columns.get_loc(column_name) + 1
                for cells in ws.iter_cols(min_col=col_idx, max_col=col_idx, min_row=2):
                    for cell in cells:
                        cell.number_format = "@"


def write_readme(
    path: Path,
    plan: pd.DataFrame,
    history: pd.DataFrame,
    master: pd.DataFrame,
    audit: pd.DataFrame,
    identity_audit: pd.DataFrame,
    rejected_audit: pd.DataFrame,
) -> None:
    matched_by_year = {}
    for year in sorted(PDF_PAGE_RANGES):
        matched_by_year[year] = int(master[f"{year}_match_level"].map(lambda x: normalize_text(x) != "").sum())

    lines = [
        "# 浙江普通类平行志愿清洗数据库",
        "",
        "## 文件",
        "",
        "- `zhejiang_parallel_volunteer_database.sqlite`: SQLite 数据库。",
        "- `volunteer_database.xlsx`: Excel 工作簿，方便直接筛选查看。",
        "- `volunteer_master_2026_with_history.csv`: 主表，一行一个 2026 平行志愿项。",
        "- `plan_2026.csv`: 2026 普通类平行计划清洗表。",
        "- `admissions_history_2023_2025.csv`: 2023-2025 普通类平行投档录取 PDF 抽取表。",
        "- `ambiguous_history_matches.csv`: 同院校同专业名存在多个可能历史匹配的疑点清单。",
        "- `college_identity_mismatches.csv`: 同院校代码但历史院校名与 2026 院校名不兼容，未自动拼回的清单。",
        "- `curated_rejections.csv`: 按校订规则从主表移出的高风险非精确历史匹配。",
        "",
        "## SQLite 表",
        "",
        "- `plan_2026`: 2026 计划表，粒度为院校代码 + 专业代码。",
        "- `admissions_history`: 历史录取抽取表，粒度为 PDF 中的院校 + 专业行。",
        "- `volunteer_master`: 已把历史录取列拼回 2026 志愿项的宽表。",
        "- `ambiguous_matches`: 未自动写入主表的歧义匹配。",
        "- `college_identity_mismatches`: 院校身份不兼容而被拦截的历史候选。",
        "- `curated_rejections`: 按校订规则不再自动写入主表的历史候选。",
        "",
        "## 统计",
        "",
        f"- 2026 计划志愿项: {len(plan):,}",
        f"- 历史抽取记录: {len(history):,}",
        f"- 歧义匹配候选: {len(audit):,}",
        f"- 院校身份不兼容拦截: {len(identity_audit):,}",
        f"- 校订排除的非精确匹配: {len(rejected_audit):,}",
    ]
    for year, count in matched_by_year.items():
        lines.append(f"- {year} 匹配到 2026 志愿项: {count:,}")
    lines.extend(
        [
            "",
            "## 重要口径",
            "",
            "- 历史 PDF 没有 2026 专业代码，因此匹配规则是保守的：先按院校代码 + 专业全名，再按去括号专业名，最后仅在同院校同年唯一包含关系时写入。",
            "- 同一院校代码跨年可能对应不同院校；当前版本会先校验院校名/alias，身份不兼容则不写入主表。",
            "- `*_match_level` 记录匹配方式；`manual_ambiguous` 表示从歧义候选中按校订规则指定拼回。",
            "- `base` 和 `contains_unique` 里被校订规则判为 DROP/UNCERTAIN 的候选已移出主表，写入 `curated_rejections.csv`。",
            "- `*_history_source_page` 是 PDF 页码，进入最终志愿单前应回查原 PDF。",
            "- 主表中空白历史列表示未找到高置信匹配，不等于该专业过去没有招生。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = read_2026_plan()
    print(f"2026 plan rows: {len(plan):,}")
    history = build_history()
    history = fill_history_college_codes(history, plan)
    master, audit, identity_audit, rejected_audit = match_history(plan, history)
    master = add_summary_columns(master)

    write_csv(OUT_DIR / "plan_2026.csv", plan)
    write_csv(OUT_DIR / "admissions_history_2023_2025.csv", history)
    write_csv(OUT_DIR / "volunteer_master_2026_with_history.csv", master)
    write_csv(OUT_DIR / "ambiguous_history_matches.csv", audit)
    write_csv(OUT_DIR / "college_identity_mismatches.csv", identity_audit)
    write_csv(OUT_DIR / "curated_rejections.csv", rejected_audit)
    write_sqlite(
        OUT_DIR / "zhejiang_parallel_volunteer_database.sqlite",
        {
            "plan_2026": plan,
            "admissions_history": history,
            "volunteer_master": master,
            "ambiguous_matches": audit,
            "college_identity_mismatches": identity_audit,
            "curated_rejections": rejected_audit,
        },
    )
    write_excel(
        OUT_DIR / "volunteer_database.xlsx",
        {
            "volunteer_master": master,
            "plan_2026": plan,
            "admissions_history": history,
            "ambiguous_matches": audit,
            "college_identity_mismatches": identity_audit,
            "curated_rejections": rejected_audit,
        },
    )
    write_readme(OUT_DIR / "README.md", plan, history, master, audit, identity_audit, rejected_audit)
    summary = {
        "plan_rows": len(plan),
        "history_rows": len(history),
        "master_rows": len(master),
        "ambiguous_rows": len(audit),
        "college_identity_mismatch_rows": len(identity_audit),
        "curated_rejection_rows": len(rejected_audit),
        "matched_by_year": {
            str(year): int(master[f"{year}_match_level"].map(lambda x: normalize_text(x) != "").sum())
            for year in sorted(PDF_PAGE_RANGES)
        },
    }
    (OUT_DIR / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
