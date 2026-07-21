# -------------------------------------------------
# 동네별 인구 피라미드 (Streamlit + Plotly)
# -------------------------------------------------
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# 페이지 기본 설정 (따뜻한 느낌을 위해 넓은 레이아웃 사용)
st.set_page_config(page_title="동네별 인구 피라미드", page_icon="🏘️", layout="wide")

# -------------------------------------------------
# 1. 데이터 불러오기 (캐시로 한 번만 다운로드)
# -------------------------------------------------
@st.cache_data(show_spinner="데이터를 불러오는 중이에요...")
def load_data():
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    # 확장자가 .gz면 pandas가 알아서 압축을 풀어서 읽어줍니다.
    df = pd.read_csv(url, compression="gzip")
    return df

df = load_data()

# -------------------------------------------------
# 2. 가장 최신 연도만 골라내기
# -------------------------------------------------
latest_year = df["연도"].max()
df_latest = df[df["연도"] == latest_year].copy()

st.title("🏘️ 동네별 인구 피라미드")
st.caption(f"📅 기준 연도: {latest_year}년")

# -------------------------------------------------
# 3. 시도 → 시군구 → 동 선택 (드롭다운 3개)
# -------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df_latest["시도"].dropna().unique())
    sido = st.selectbox("시도 선택", sido_list)

with col2:
    sigungu_list = sorted(
        df_latest.loc[df_latest["시도"] == sido, "시군구"].dropna().unique()
    )
    sigungu = st.selectbox("시군구 선택", sigungu_list)

with col3:
    dong_list = sorted(
        df_latest.loc[
            (df_latest["시도"] == sido) & (df_latest["시군구"] == sigungu), "동"
        ]
        .dropna()
        .unique()
    )
    dong = st.selectbox("동 선택", dong_list)

# 선택한 동네 한 행만 뽑기
row_df = df_latest[
    (df_latest["시도"] == sido)
    & (df_latest["시군구"] == sigungu)
    & (df_latest["동"] == dong)
]

if row_df.empty:
    st.warning("선택한 동네의 데이터가 없어요. 다른 동네를 골라보세요.")
    st.stop()

row = row_df.iloc[0]

# -------------------------------------------------
# 4. 나이 순서를 0세부터 100세 이상까지 '고정'해서 만들기
#    (이 리스트 순서가 그대로 세로축 순서가 됩니다)
# -------------------------------------------------
ages = [f"{i}세" for i in range(100)] + ["100세 이상"]

# 남자는 음수로 만들어서 왼쪽, 여자는 양수로 만들어서 오른쪽에 그림
male_values = [-row.get(f"남_{age}", 0) for age in ages]
female_values = [row.get(f"여_{age}", 0) for age in ages]

# -------------------------------------------------
# 5. Plotly로 인구 피라미드 그리기
# -------------------------------------------------
fig = go.Figure()

fig.add_trace(
    go.Bar(
        y=ages,
        x=male_values,
        name="남자",
        orientation="h",
        marker_color="#6FA3D9",  # 따뜻한 톤의 파란색
        hovertemplate="나이: %{y}<br>남자: %{customdata}명<extra></extra>",
        customdata=[abs(v) for v in male_values],
    )
)

fig.add_trace(
    go.Bar(
        y=ages,
        x=female_values,
        name="여자",
        orientation="h",
        marker_color="#F4978E",  # 살구색 톤
        hovertemplate="나이: %{y}<br>여자: %{x}명<extra></extra>",
    )
)

fig.update_layout(
    title=f"{sido} {sigungu} {dong} 인구 피라미드 ({latest_year}년)",
    barmode="overlay",
    bargap=0.1,
    plot_bgcolor="#FFFBF5",   # 따뜻한 크림색 배경
    paper_bgcolor="#FFFBF5",
    xaxis_title="인구 수 (명)",
    yaxis_title="나이",
    legend_title="성별",
)

# x축은 음수/양수 대신 절댓값으로 보이게(라벨만 바꿈)
max_val = max(max(abs(v) for v in male_values), max(female_values)) if len(ages) > 0 else 0
tick_step = max(1, round(max_val / 4, -1) if max_val > 0 else 1)
tickvals = list(range(-int(max_val), int(max_val) + 1, int(tick_step) if tick_step else 1))
fig.update_xaxes(
    tickvals=tickvals,
    ticktext=[str(abs(v)) for v in tickvals],
)

# ---------------------------------------------------------------
# ⭐ 핵심: 세로축(나이) 순서를 '고정 배열'로 지정
# ages 리스트의 첫 번째("0세")가 맨 아래, 마지막("100세 이상")이 맨 위로 옵니다.
# autorange 뒤집기나 값 정렬 옵션은 사용하지 않습니다.
# ---------------------------------------------------------------
fig.update_yaxes(
    categoryorder="array",
    categoryarray=ages,
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# 6. 세로축 순서 확인용 안내 (그림 아래 체크 문구)
# -------------------------------------------------
st.info(
    "✅ 그래프의 세로축을 확인해보세요! 맨 아래 눈금이 **0세**, 맨 위 눈금이 **100세 이상**이어야 합니다."
)

# -------------------------------------------------
# 7. 지표 카드: 총인구, 평균연령, 고령화율
# -------------------------------------------------
age_cols_all = [f"{gender}_{age}" for gender in ("남", "여") for age in ages]
total_pop = sum(row.get(c, 0) for c in age_cols_all)

age_nums = list(range(101))  # 100세 이상은 100으로 취급
pop_by_age = [row.get(f"남_{a}", 0) + row.get(f"여_{a}", 0) for a in ages]
mean_age = sum(n * p for n, p in zip(age_nums, pop_by_age)) / total_pop
elderly_pop = sum(p for n, p in zip(age_nums, pop_by_age) if n >= 65)
aging_rate = elderly_pop / total_pop * 100

card1, card2, card3 = st.columns(3)
card1.metric("총인구", f"{total_pop:,.0f}명")
card2.metric("평균연령", f"{mean_age:.1f}세")
card3.metric(
    "고령화율 (65세 이상)",
    f"{aging_rate:.1f}%",
    delta="⚠️ 20% 이상" if aging_rate >= 20 else None,
    delta_color="inverse",
)

if aging_rate >= 20:
    st.caption("이 동네는 어르신이 많은 편이에요.")
else:
    st.caption("이 동네는 아이·젊은 층 비중이 높은 편이에요.")
