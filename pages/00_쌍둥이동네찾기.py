
import os
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 이 스크립트와 같은 폴더에 있는 CSV 파일명 (원본 그대로)
DATA_FILE = "202606_202606_연령별인구현황_월간.csv"

# 색맹 안전성이 검증된 범주형 팔레트 (라이트/다크 각각 별도 스텝)
PALETTE_LIGHT = ["#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a", "#eb6834"]
PALETTE_DARK = ["#3987e5", "#008300", "#d55181", "#c98500", "#199e70", "#d95926"]

st.set_page_config(page_title="지역별 연령 인구 구조", page_icon="📊", layout="wide")


def palette() -> list:
    """스트림릿 테마(라이트/다크)에 맞는 색상 팔레트를 반환."""
    try:
        if st.context.theme.type == "dark":
            return PALETTE_DARK
    except Exception:
        pass
    return PALETTE_LIGHT


@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    for encoding in ("cp949", "utf-8-sig", "utf-8"):
        try:
            df = pd.read_csv(path, encoding=encoding, low_memory=False)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSV 인코딩을 인식하지 못했습니다 (cp949 / utf-8 모두 실패)")

    df = df.rename(columns={df.columns[0]: "행정구역"})
    df["행정구역"] = df["행정구역"].astype(str).str.strip()

    # 숫자 컬럼이 "9,289,813" 형태의 문자열이라 콤마를 제거하고 숫자로 변환
    numeric = {
        col: pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False), errors="coerce"
        )
        for col in df.columns[1:]
    }
    return pd.concat([df[["행정구역"]], pd.DataFrame(numeric)], axis=1)


def parse_age_columns(columns: list) -> dict:
    """'2026년06월_계_35세' 형태의 컬럼명을 {성별: {연령: 컬럼명}}으로 정리."""
    result = {"계": {}, "남": {}, "여": {}}
    for col in columns[1:]:
        for gender in ("계", "남", "여"):
            marker = f"_{gender}_"
            if marker not in col or "총인구수" in col or "연령구간인구수" in col:
                continue
            label = col.split(marker)[-1].replace("세 이상", "+").replace("세", "").strip()
            age = 100 if label == "100+" else (int(label) if label.isdigit() else None)
            if age is not None:
                result[gender][age] = col
    return result


def admin_level(name: str) -> str:
    """행정구역 코드(시도 2자리 + 시군구 3자리 + 읍면동 5자리)로 행정단위를 판별."""
    found = re.search(r"\((\d{10})\)", name)
    if not found:
        return "읍면동"
    code = found.group(1)
    if code[2:] == "0" * 8:
        return "시도"
    if code[5:] == "0" * 5:
        return "시군구"
    return "읍면동"


@st.cache_data(show_spinner=False)
def build_profiles(path: str):
    """지역별 연령 구성비(%) 행렬과 총인구·행정단위를 미리 계산해 둔다."""
    df = load_data(path)
    age_cols = parse_age_columns(list(df.columns))
    ages = sorted(age_cols["계"])

    counts = df[[age_cols["계"][a] for a in ages]].to_numpy(dtype=float)
    totals = counts.sum(axis=1)

    # 인구 규모가 아닌 '구조'를 비교하기 위해 각 지역을 구성비(%)로 정규화
    profiles = np.zeros_like(counts)
    has_people = totals > 0
    profiles[has_people] = counts[has_people] / totals[has_people, None] * 100

    levels = np.array([admin_level(n) for n in df["행정구역"]])
    return df, age_cols, ages, profiles, totals, levels, has_people


data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATA_FILE)

if not os.path.exists(data_path):
    st.error(f"'{DATA_FILE}' 파일을 찾을 수 없습니다. 이 스크립트와 같은 폴더에 CSV 파일을 넣어주세요.")
    st.stop()

try:
    data, age_cols, ages, profiles, totals, levels, has_people = build_profiles(data_path)
except Exception as e:
    st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
    st.stop()

if not ages:
    st.error("연령별 컬럼(예: '2026년06월_계_0세')을 찾지 못했습니다. 파일 형식을 확인해 주세요.")
    st.stop()

st.title("📊 지역별 연령 인구 구조")
st.caption("행정안전부 주민등록 연령별 인구현황(월간) 데이터로, 선택한 지역의 연령 구조와 전국에서 가장 비슷한 지역을 찾아봅니다.")

st.divider()

# ── 지역 선택: 검색어(직접 입력)로 후보를 좁히고, 드롭다운에서 최종 선택 ──
left, right = st.columns([1, 2])
with left:
    keyword = st.text_input("🔍 지역명 검색 (직접 입력)", placeholder="예: 종로구, 해운대, 봉화")
with right:
    all_regions = data["행정구역"].tolist()
    regions = [r for r in all_regions if keyword.strip() in r] if keyword.strip() else all_regions
    if not regions:
        st.warning("검색 결과가 없습니다. 다른 검색어를 입력해 보세요.")
        st.stop()
    region = st.selectbox("지역 선택 (읍면동까지 선택 가능)", options=regions, index=0)

target = all_regions.index(region)
labels = ["100+" if a == 100 else str(a) for a in ages]
colors = palette()

tab_structure, tab_similar = st.tabs(["📈 인구 구조", "🔎 비슷한 지역 Top 5"])


# ─────────────────────────── 탭 1: 선택 지역의 인구 구조 ───────────────────────────
with tab_structure:
    options = st.columns(2)
    split_gender = options[0].checkbox("남/여 나눠서 보기", value=True)
    as_ratio = options[1].checkbox("전체 대비 비율(%)로 보기", value=False)

    row = data.iloc[target]

    def series_for(gender: str) -> list:
        values = [row[age_cols[gender][a]] for a in ages]
        if as_ratio:
            total = sum(v for v in values if pd.notna(v))
            if total:
                values = [v / total * 100 for v in values]
        return values

    fig = go.Figure()
    if split_gender:
        fig.add_trace(go.Scatter(x=labels, y=series_for("남"), mode="lines", name="남",
                                 line=dict(color=colors[0], width=2)))
        fig.add_trace(go.Scatter(x=labels, y=series_for("여"), mode="lines", name="여",
                                 line=dict(color=colors[5], width=2)))
    else:
        fig.add_trace(go.Scatter(x=labels, y=series_for("계"), mode="lines", name="전체",
                                 line=dict(color=colors[0], width=2)))

    fig.update_layout(
        title=f"{region} 연령별 인구 구조",
        xaxis_title="연령(세)",
        yaxis_title="비율(%)" if as_ratio else "인구수(명)",
        hovermode="x unified",
        height=520,
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    )
    fig.update_xaxes(tickmode="linear", dtick=5)
    st.plotly_chart(fig, use_container_width=True)

    def total_of(gender: str):
        matches = [c for c in data.columns if c.endswith(f"_{gender}_총인구수")]
        return row[matches[0]] if matches else None

    m = st.columns(4)
    total, male, female = total_of("계"), total_of("남"), total_of("여")
    m[0].metric("총인구수", f"{total:,.0f}명" if pd.notna(total) else "-")
    m[1].metric("남성", f"{male:,.0f}명" if pd.notna(male) else "-")
    m[2].metric("여성", f"{female:,.0f}명" if pd.notna(female) else "-")
    elderly = sum(row[age_cols["계"][a]] for a in ages if a >= 65)
    m[3].metric("65세 이상 비율", f"{elderly / total * 100:.1f}%" if total else "-")


# ──────────────────── 탭 2: 인구 구조가 가장 비슷한 지역 Top 5 ────────────────────
with tab_similar:
    if not has_people[target]:
        st.warning("선택한 지역은 인구가 0명이라 비교할 수 없습니다. 다른 지역을 선택해 주세요.")
        st.stop()

    controls = st.columns([2, 2])
    same_level_only = controls[0].toggle(
        f"같은 행정단위({levels[target]})끼리만 비교", value=True,
        help="끄면 시도·시군구·읍면동을 가리지 않고 전국 모든 지역과 비교합니다.",
    )
    min_pop = controls[1].number_input(
        "비교 대상 최소 인구수", min_value=0, max_value=100000, value=1000, step=500,
        help="인구가 아주 적은 지역은 연령 구성비가 들쭉날쭉해 비교에서 빼는 편이 좋습니다.",
    )

    # 연령 구성비 벡터 사이의 유클리드 거리 = 작을수록 인구 구조가 비슷함
    distances = np.sqrt(((profiles - profiles[target]) ** 2).sum(axis=1))

    candidates = has_people & (totals >= min_pop)
    candidates[target] = False
    if same_level_only:
        candidates &= levels == levels[target]

    pool = np.where(candidates)[0]
    if len(pool) == 0:
        st.warning("비교할 지역이 없습니다. 최소 인구수를 낮추거나 행정단위 조건을 꺼 보세요.")
        st.stop()

    top5 = pool[np.argsort(distances[pool])][:5]

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=labels, y=profiles[target], mode="lines", name=f"⭐ {region}",
        line=dict(color=colors[0], width=4),
    ))
    for rank, idx in enumerate(top5, start=1):
        fig2.add_trace(go.Scatter(
            x=labels, y=profiles[idx], mode="lines", name=f"{rank}. {all_regions[idx]}",
            line=dict(color=colors[rank], width=2),
        ))

    fig2.update_layout(
        title=f"{region} 와(과) 인구 구조가 가장 비슷한 지역 Top 5",
        xaxis_title="연령(세)",
        yaxis_title="해당 연령 비율(%)",
        hovermode="x unified",
        height=560,
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0),
    )
    fig2.update_xaxes(tickmode="linear", dtick=5)
    st.plotly_chart(fig2, use_container_width=True)

    st.caption(
        "인구 '규모'가 아니라 '구조'를 비교하려고 각 지역을 연령별 구성비(%)로 바꾼 뒤, "
        "구성비 사이의 거리가 가장 가까운 지역을 찾았습니다. 거리가 0에 가까울수록 인구 구조가 닮았습니다."
    )

    def summarize(idx: int) -> dict:
        counts = profiles[idx] * totals[idx] / 100
        return {
            "지역": all_regions[idx],
            "행정단위": levels[idx],
            "총인구수": int(totals[idx]),
            "65세 이상 비율(%)": round(float(counts[65:].sum() / totals[idx] * 100), 1),
            "구조 차이(거리)": round(float(distances[idx]), 2),
        }

    table = pd.DataFrame([summarize(target)] + [summarize(i) for i in top5])
    table.insert(0, "순위", ["선택 지역"] + [f"{i}위" for i in range(1, len(top5) + 1)])
    st.dataframe(table, use_container_width=True, hide_index=True)
