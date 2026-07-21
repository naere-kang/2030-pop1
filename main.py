
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# 이 스크립트와 같은 폴더에 있는 CSV 파일명 (원본 그대로)
DATA_FILE = "202606_202606_연령별인구현황_월간.csv"

st.set_page_config(page_title="지역별 연령 인구 구조", page_icon="📊", layout="wide")

st.title("📊 지역별 연령 인구 구조")
st.caption("행정안전부 주민등록 연령별 인구현황(월간) 데이터를 바탕으로, 선택한 지역의 연령별 인구 구조를 꺾은선 그래프로 보여줍니다.")


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
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False), errors="coerce"
        )
    return df


@st.cache_data(show_spinner=False)
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


data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DATA_FILE)

if not os.path.exists(data_path):
    st.error(f"'{DATA_FILE}' 파일을 찾을 수 없습니다. 이 스크립트와 같은 폴더에 CSV 파일을 넣어주세요.")
    st.stop()

try:
    data = load_data(data_path)
except Exception as e:
    st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
    st.stop()

age_cols = parse_age_columns(list(data.columns))
if not age_cols["계"]:
    st.error("연령별 컬럼(예: '2026년06월_계_0세')을 찾지 못했습니다. 파일 형식을 확인해 주세요.")
    st.stop()

st.divider()

# ── 지역 선택: 검색어(직접 입력)로 후보를 좁히고, 드롭다운에서 최종 선택 ──
left, right = st.columns([1, 2])
with left:
    keyword = st.text_input("🔍 지역명 검색 (직접 입력)", placeholder="예: 종로구, 해운대, 수원")
with right:
    regions = data["행정구역"].dropna().tolist()
    if keyword.strip():
        regions = [r for r in regions if keyword.strip() in r]
    if not regions:
        st.warning("검색 결과가 없습니다. 다른 검색어를 입력해 보세요.")
        st.stop()
    region = st.selectbox("지역 선택", options=regions, index=0)

options = st.columns(2)
split_gender = options[0].checkbox("남/여 나눠서 보기", value=True)
as_ratio = options[1].checkbox("전체 대비 비율(%)로 보기", value=False)

st.divider()

row = data.loc[data["행정구역"] == region].iloc[0]
ages = sorted(age_cols["계"])
labels = ["100+" if a == 100 else str(a) for a in ages]


def series_for(gender: str) -> list:
    values = [row[age_cols[gender][a]] for a in ages]
    if as_ratio:
        total = sum(v for v in values if pd.notna(v))
        if total:
            values = [v / total * 100 for v in values]
    return values


fig = go.Figure()
if split_gender:
    fig.add_trace(go.Scatter(x=labels, y=series_for("남"), mode="lines", name="남", line=dict(color="#3B82F6", width=2)))
    fig.add_trace(go.Scatter(x=labels, y=series_for("여"), mode="lines", name="여", line=dict(color="#EF4444", width=2)))
else:
    fig.add_trace(go.Scatter(x=labels, y=series_for("계"), mode="lines", name="전체", line=dict(color="#3B82F6", width=2)))

fig.update_layout(
    title=f"{region} 연령별 인구 구조",
    xaxis_title="연령(세)",
    yaxis_title="비율(%)" if as_ratio else "인구수(명)",
    hovermode="x unified",
    height=520,
    margin=dict(l=20, r=20, t=60, b=20),
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

with st.expander("📄 원본 데이터 보기"):
    st.dataframe(data.loc[data["행정구역"] == region].T, use_container_width=True)
