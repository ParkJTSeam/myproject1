import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="전국 고령화 & 연령별 인구 탐색기",
    page_icon="🗺️",
    layout="wide"
)

# 2. 데이터 로딩 함수 (전체 연도 데이터 활용)
@st.cache_data
def load_full_population_data():
    """전체 연도의 인구 데이터를 불러오고 가공합니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # 코드는 5자리 시군구 조회를 위해 문자열(str) 형태로 로드
    df = pd.read_csv(url, compression='gzip', dtype={'코드': str})
    
    # 시군구 코드(5자리) 생성
    df['sigungu_code'] = df['코드'].str.slice(0, 5)
    
    # 전체/노인/10대 인구 열 구분
    total_pop_cols = [col for col in df.columns if col.startswith('계_')]
    
    # 65세 이상 열
    elderly_cols = []
    # 10대 (10세 ~ 19세) 열
    teen_cols = []
    
    for col in total_pop_cols:
        age_str = col.replace('계_', '').replace('세', '').replace(' 이상', '')
        if age_str.isdigit():
            age = int(age_str)
            if age >= 65:
                elderly_cols.append(col)
            elif 10 <= age <= 19:
                teen_cols.append(col)
        elif col == '계_100세 이상':
            elderly_cols.append(col)
            
    # 연도별, 행정동별 주요 인구 합산
    df['total_pop'] = df[total_pop_cols].sum(axis=1)
    df['elderly_pop'] = df[elderly_cols].sum(axis=1)
    df['teen_pop'] = df[teen_cols].sum(axis=1)
    
    # 시군구 단위로 집계
    grouped = df.groupby(['연도', 'sigungu_code']).agg({
        '시도': 'first',
        '시군구': 'first',
        'total_pop': 'sum',
        'elderly_pop': 'sum',
        'teen_pop': 'sum'
    }).reset_index()
    
    # 고령화율(%) 및 10대 비율(%) 계산
    grouped['elderly_ratio'] = (grouped['elderly_pop'] / grouped['total_pop'] * 100).round(1)
    grouped['teen_ratio'] = (grouped['teen_pop'] / grouped['total_pop'] * 100).round(1)
    
    return grouped

@st.cache_data
def load_geojson():
    """전국 시군구 경계 GeoJSON 데이터를 불러옵니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url)
    return response.json()

# 데이터 로드
with st.spinner("전국 인구 데이터를 불러오는 중입니다..."):
    df_pop = load_full_population_data()
    geojson_data = load_geojson()

# 세션 상태 초기화 (클릭 및 선택 관리)
if 'selected_sido' not in st.session_state:
    st.session_state.selected_sido = "전체"
if 'selected_sigungu' not in st.session_state:
    st.session_state.selected_sigungu = "전체"
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = int(df_pop['연도'].max())

# --- [사이드바 UI: 탐색 제어] ---
st.sidebar.title("🔍 지역 및 연도 탐색")

# 1. 시/도 선택
sido_list = ["전체"] + sorted(list(df_pop['시도'].dropna().unique()))
selected_sido = st.sidebar.selectbox("1. 시·도 선택 (확대)", sido_list, index=sido_list.index(st.session_state.selected_sido))
st.session_state.selected_sido = selected_sido

# 2. 시/군/구 선택 (시/도가 선택되었을 때 활성화)
if selected_sido != "전체":
    available_sigungu = ["전체"] + sorted(list(df_pop[df_pop['시도'] == selected_sido]['시군구'].dropna().unique()))
    selected_sigungu = st.sidebar.selectbox("2. 시·군·구 선택", available_sigungu, index=available_sigungu.index(st.session_state.selected_sigungu) if st.session_state.selected_sigungu in available_sigungu else 0)
    st.session_state.selected_sigungu = selected_sigungu
else:
    st.session_state.selected_sigungu = "전체"

# 3. 연도 선택 UI
year_list = sorted(list(df_pop['연도'].unique()), reverse=True)
selected_year = st.sidebar.select_slider("3. 연도 선택", options=sorted(year_list), value=st.session_state.selected_year)
st.session_state.selected_year = selected_year

st.sidebar.markdown("---")
st.sidebar.info("💡 Tip: 사이드바에서 시·도를 선택하면 지도가 해당 위치로 자동 확대되며, 시·군·구 및 연도를 선택하여 상세 인구를 확인할 수 있습니다.")


# --- [메인 화면 구성] ---
st.title("🗺️ 전국 시군구 고령화 지도 & 10대 인구 탐색기")

# 선택된 연도의 데이터 필터링
df_current_year = df_pop[df_pop['연도'] == selected_year].copy()

# 고령화율 5단계 범주화 (19%, 23%, 28%, 38% 기준)
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_current_year['ratio_group'] = pd.cut(
    df_current_year['elderly_ratio'], 
    bins=bins, 
    labels=labels, 
    right=False
)

color_discrete_map = {
    '19% 미만': '#fef0d9',
    '19% 이상 ~ 23% 미man': '#fdd49e',
    '23% 이상 ~ 28% 미만': '#fdbb84',
    '28% 이상 ~ 38% 미만': '#fc8d59',
    '38% 이상': '#d7301f'
}

# 시/도 선택에 따른 중심 좌표 및 Zoom 설정 (확대 효과)
sido_centers = {
    "전체": {"lat": 35.8, "lon": 127.8, "zoom": 6.2},
    "서울특별시": {"lat": 37.5665, "lon": 126.9780, "zoom": 9.5},
    "부산광역시": {"lat": 35.1796, "lon": 129.0756, "zoom": 9.5},
    "대구광역시": {"lat": 35.8714, "lon": 128.6014, "zoom": 9.0},
    "인천광역시": {"lat": 37.4563, "lon": 126.7052, "zoom": 9.0},
    "광주광역시": {"lat": 35.1595, "lon": 126.8526, "zoom": 10.0},
    "대전광역시": {"lat": 36.3504, "lon": 127.3845, "zoom": 10.0},
    "울산광역시": {"lat": 35.5384, "lon": 129.3114, "zoom": 9.8},
    "세종특별자치시": {"lat": 36.4800, "lon": 127.2890, "zoom": 10.5},
    "경기도": {"lat": 37.4138, "lon": 127.5183, "zoom": 8.2},
    "강원특별자치도": {"lat": 37.8228, "lon": 128.1555, "zoom": 7.8},
    "충청북도": {"lat": 36.6357, "lon": 127.4912, "zoom": 8.2},
    "충청남도": {"lat": 36.5184, "lon": 126.8000, "zoom": 8.3},
    "전북특별자치도": {"lat": 35.7175, "lon": 127.1530, "zoom": 8.3},
    "전라남도": {"lat": 34.8161, "lon": 126.4629, "zoom": 8.0},
    "경상북도": {"lat": 36.5760, "lon": 128.5056, "zoom": 7.8},
    "경상남도": {"lat": 35.4606, "lon": 128.2132, "zoom": 8.2},
    "제주특별자치도": {"lat": 33.4890, "lon": 126.4983, "zoom": 9.2}
}

view_config = sido_centers.get(st.session_state.selected_sido, sido_centers["전체"])

# 지도 표현용 데이터 필터링
if st.session_state.selected_sido != "전체":
    map_data = df_current_year[df_current_year['시도'] == st.session_state.selected_sido]
else:
    map_data = df_current_year

# Plotly 지도 생성
fig = px.choropleth_mapbox(
    map_data,
    geojson=geojson_data,
    locations='sigungu_code',
    featureidkey="properties.코드",
    color='ratio_group',
    color_discrete_map=color_discrete_map,
    category_orders={'ratio_group': labels},
    center={"lat": view_config["lat"], "lon": view_config["lon"]},
    zoom=view_config["zoom"],
    hover_name='시군구',
    hover_data={
        '시도': True,
        'elderly_ratio': ':.1f%',
        'sigungu_code': False,
        'ratio_group': False
    },
    labels={'elderly_ratio': '고령화율', 'ratio_group': '고령화 비율 구간'}
)

fig.update_layout(
    mapbox_style="white-bg",
    mapbox_layers=[{
        "below": 'traces',
        "sourcetype": "raster",
        "source": ["data:image/png;base64,iVBORw0KGgoAAAANSU50EUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="]
    }],
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    transition_duration=500, # 시/도 변경 시 부드러운 애니메이션 전환 효과
    legend=dict(
        title=dict(text="<b>고령화율 구간</b>"),
        yanchor="top", y=0.98, xanchor="left", x=0.02,
        bgcolor="rgba(255, 255, 255, 0.8)"
    )
)

fig.update_traces(
    marker_line_width=0.8,
    marker_line_color="#333333"
)

# 지도 출력
st.plotly_chart(fig, use_container_width=True)


# --- [선택된 지역 & 연도의 10대 인구 픽토그램 시각화] ---
st.markdown("---")

if st.session_state.selected_sido != "전체" and st.session_state.selected_sigungu != "전체":
    # 특정 시/군/구가 모두 선택된 경우 상세 인구 정보 표시
    target_data = df_pop[
        (df_pop['시도'] == st.session_state.selected_sido) & 
        (df_pop['시군구'] == st.session_state.selected_sigungu) & 
        (df_pop['연도'] == st.session_state.selected_year)
    ]
    
    if not target_data.empty:
        row = target_data.iloc[0]
        total_pop = int(row['total_pop'])
        teen_pop = int(row['teen_pop'])
        teen_ratio = row['teen_ratio']
        
        st.subheader(f"📊 {row['시도']} {row['시군구']} ({st.session_state.selected_year}년) 10대 인구 현황")
        
        # 지표 출력
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("총 인구수", f"{total_pop:,} 명")
        m_col2.metric("10대 인구수 (10~19세)", f"{teen_pop:,} 명")
        m_col3.metric("10대 인구 비율", f"{teen_ratio:.1f}%")
        
        st.write("#### 👦👧 10대 인구 비율 픽토그램 (1개 당 = 1%)")
        
        # 픽토그램 생성 (1%당 아이콘 1개로 변환)
        icon_count = int(round(teen_ratio))
        max_icons = 50  # 최대 아이콘 표현 수
        
        # 10대 표현 픽토그램 아이콘 (🧑) 및 비어있는 백그라운드 아이콘(⚪)
        pictogram_html = "<div style='font-size: 28px; line-height: 1.6; word-wrap: break-word; background-color: #f8f9fa; padding: 15px; border-radius: 10px;'>"
        for i in range(1, 100 + 1):
            if i <= icon_count:
                pictogram_html += "🧑 "
            else:
                pictogram_html += "<span style='opacity: 0.2;'>⚪</span> "
            if i % 10 == 0:
                pictogram_html += "<br>"
        pictogram_html += "</div>"
        
        st.components.v1.html(pictogram_html, height=360)
        st.caption("※ 위 픽토그램은 해당 지역 전체 인구 중 10대 인구의 비율(%)을 100개의 점으로 나타낸 것입니다.")

elif st.session_state.selected_sido != "전체":
    st.info(f"👉 왼쪽 사이드바에서 **[{st.session_state.selected_sido}]** 내의 **시·군·구**를 선택하시면, 선택한 연도의 **10대 인구 픽토그램 시각화**를 확인할 수 있습니다.")
else:
    st.info("👉 왼쪽 사이드바에서 **시·도** 및 **시·군·구**를 선택하시면 지도가 해당 위치로 확대되며 상세 10대 인구 픽토그램이 표시됩니다.")
