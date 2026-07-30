import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="전국 연령구간별 인구 탐색기",
    page_icon="🗺️",
    layout="wide"
)

# 2. 데이터 로딩 함수 (전체 연도 및 전체 연령 데이터 가공)
@st.cache_data
def load_full_population_data():
    """전체 연도의 인구 데이터를 불러와 10대~80대 이상 연령 구간별로 집계합니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # 코드는 5자리 시군구 조회를 위해 문자열(str) 형태로 로드
    df = pd.read_csv(url, compression='gzip', dtype={'코드': str})
    
    # 시군구 코드(5자리) 생성
    df['sigungu_code'] = df['코드'].str.slice(0, 5)
    
    # 전체/노인/연령대별 인구 열 구분
    total_pop_cols = [col for col in df.columns if col.startswith('계_')]
    
    # 65세 이상 고령 인구 열
    elderly_cols = []
    for col in total_pop_cols:
        age_str = col.replace('계_', '').replace('세', '').replace(' 이상', '')
        if age_str.isdigit():
            if int(age_str) >= 65:
                elderly_cols.append(col)
        elif col == '계_100세 이상':
            elderly_cols.append(col)
            
    # 전체 및 고령 인구 합산
    df['total_pop'] = df[total_pop_cols].sum(axis=1)
    df['elderly_pop'] = df[elderly_cols].sum(axis=1)
    
    # 연령 구간 정의 (10대, 20대, 30대, 40대, 50대, 60대, 70대 이상)
    age_groups = {
        '10대': range(10, 20),
        '20대': range(20, 30),
        '30대': range(30, 40),
        '40대': range(40, 50),
        '50대': range(50, 60),
        '60대': range(60, 70),
        '70대 이상': range(70, 101)
    }
    
    for group_name, age_range in age_groups.items():
        m_cols = [f'남_{age}세' for age in age_range if f'남_{age}세' in df.columns]
        f_cols = [f'여_{age}세' for age in age_range if f'여_{age}세' in df.columns]
        if group_name == '70대 이상' and '남_100세 이상' in df.columns:
            m_cols.append('남_100세 이상')
            f_cols.append('여_100세 이상')
            
        df[f'{group_name}_남_pop'] = df[m_cols].sum(axis=1)
        df[f'{group_name}_여_pop'] = df[f_cols].sum(axis=1)
        df[f'{group_name}_total_pop'] = df[f'{group_name}_남_pop'] + df[f'{group_name}_여_pop']
    
    # 시군구 단위 집계 사전
    agg_dict = {
        '시도': 'first',
        '시군구': 'first',
        'total_pop': 'sum',
        'elderly_pop': 'sum'
    }
    
    for group_name in age_groups.keys():
        agg_dict[f'{group_name}_total_pop'] = 'sum'
        agg_dict[f'{group_name}_남_pop'] = 'sum'
        agg_dict[f'{group_name}_여_pop'] = 'sum'
        
    # 0세~99세 및 100세 이상 세분화 열 추가
    for age in range(0, 100):
        if f'계_{age}세' in df.columns: agg_dict[f'계_{age}세'] = 'sum'
        if f'남_{age}세' in df.columns: agg_dict[f'남_{age}세'] = 'sum'
        if f'여_{age}세' in df.columns: agg_dict[f'여_{age}세'] = 'sum'
    
    grouped = df.groupby(['연도', 'sigungu_code']).agg(agg_dict).reset_index()
    
    # 고령화율(%) 계산
    grouped['elderly_ratio'] = (grouped['elderly_pop'] / grouped['total_pop'] * 100).round(1)
    
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

# 세션 상태 초기화
if 'selected_sido' not in st.session_state:
    st.session_state.selected_sido = "전체"
if 'selected_sigungu' not in st.session_state:
    st.session_state.selected_sigungu = "전체"
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = int(df_pop['연도'].max())
if 'selected_age_group' not in st.session_state:
    st.session_state.selected_age_group = "10대"

# --- [메인 화면 구성] ---
st.title("🗺️ 전국 시군구 고령화 지도 & 연령대별 인구 탐색기")

# 시/도 선택에 따른 중심 좌표 및 Zoom 설정
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

# 선택된 연도의 데이터 필터링
df_current_year = df_pop[df_pop['연도'] == st.session_state.selected_year].copy()

# 고령화율 5단계 범주화 (19%, 23%, 28%, 38% 기준)
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_current_year['ratio_group'] = pd.cut(
    df_current_year['elderly_ratio'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# 규칙 3: 지도 표기 색상을 Green 컬러 그라데이션 단계로 변경
green_color_discrete_map = {
    '19% 미만': '#edf8e9',
    '19% 이상 ~ 23% 미만': '#bae4b3',
    '23% 이상 ~ 28% 미만': '#74c476',
    '28% 이상 ~ 38% 미만': '#31a354',
    '38% 이상': '#006d2c'
}

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
    color_discrete_map=green_color_discrete_map,
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

# 규칙 2: 지도 좌측 상단 범례의 글자 폰트 색상을 검정(#000000)으로 설정
# 규칙 4: 드롭다운 선택 시 지도 이미지 표시 단계별 애니메이션 시간 설정 (3초 = 3000ms)
fig.update_layout(
    mapbox_style="white-bg",
    mapbox_layers=[{
        "below": 'traces',
        "sourcetype": "raster",
        "source": ["data:image/png;base64,iVBORw0KGgoAAAANSU50EUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="]
    }],
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    transition_duration=3000,  # 규칙 4: 단계별 애니메이션 3초 (3000ms)
    legend=dict(
        title=dict(text="<b>고령화율 구간</b>", font=dict(color="#000000", size=13)),
        font=dict(color="#000000", size=12),  # 규칙 2: 범례 폰트 검정색
        yanchor="top", y=0.98, xanchor="left", x=0.02,
        bgcolor="rgba(255, 255, 255, 0.9)"
    )
)

fig.update_traces(
    marker_line_width=0.8,
    marker_line_color="#222222"
)

# 지도 출력
st.plotly_chart(fig, use_container_width=True)


# --- [규칙 1: 하단 드롭다운에 연령 구간 메뉴 추가] ---
st.markdown("### 📍 지역, 연도 및 연령 구간 선택")

col_sido, col_sigungu, col_year, col_age = st.columns(4)

with col_sido:
    sido_list = ["전체"] + sorted(list(df_pop['시도'].dropna().unique()))
    selected_sido = st.selectbox(
        "시·도 선택", 
        sido_list, 
        index=sido_list.index(st.session_state.selected_sido)
    )
    if selected_sido != st.session_state.selected_sido:
        st.session_state.selected_sido = selected_sido
        st.session_state.selected_sigungu = "전체"
        st.rerun()

with col_sigungu:
    if st.session_state.selected_sido != "전체":
        available_sigungu = ["전체"] + sorted(list(df_pop[df_pop['시도'] == st.session_state.selected_sido]['시군구'].dropna().unique()))
    else:
        available_sigungu = ["전체"]
    
    selected_sigungu = st.selectbox(
        "시·군·구 선택", 
        available_sigungu, 
        index=available_sigungu.index(st.session_state.selected_sigungu) if st.session_state.selected_sigungu in available_sigungu else 0
    )
    if selected_sigungu != st.session_state.selected_sigungu:
        st.session_state.selected_sigungu = selected_sigungu
        st.rerun()

with col_year:
    year_list = sorted(list(df_pop['연도'].unique()), reverse=True)
    selected_year = st.selectbox(
        "연도 선택", 
        year_list, 
        index=year_list.index(st.session_state.selected_year)
    )
    if selected_year != st.session_state.selected_year:
        st.session_state.selected_year = selected_year
        st.rerun()

with col_age:
    # 규칙 1: 연령 구간 선택 옵션 추가 (10대, 20대, 30대, 40대, 50대, 60대, 70대 이상)
    age_group_list = ["10대", "20대", "30대", "40대", "50대", "60대", "70대 이상"]
    selected_age_group = st.selectbox(
        "연령 구간 선택",
        age_group_list,
        index=age_group_list.index(st.session_state.selected_age_group)
    )
    if selected_age_group != st.session_state.selected_age_group:
        st.session_state.selected_age_group = selected_age_group
        st.rerun()

st.markdown("---")

# --- [선택 연령 구간 인구 현황 및 성별 분리 픽토그램/세부 그래프] ---
curr_age_group = st.session_state.selected_age_group

if st.session_state.selected_sido != "전체" and st.session_state.selected_sigungu != "전체":
    target_data = df_pop[
        (df_pop['시도'] == st.session_state.selected_sido) & 
        (df_pop['시군구'] == st.session_state.selected_sigungu) & 
        (df_pop['연도'] == st.session_state.selected_year)
    ]
    
    if not target_data.empty:
        row = target_data.iloc[0]
        total_pop = int(row['total_pop'])
        
        target_total_pop = int(row[f'{curr_age_group}_total_pop'])
        target_male_pop = int(row[f'{curr_age_group}_남_pop'])
        target_female_pop = int(row[f'{curr_age_group}_여_pop'])
        
        target_ratio = (target_total_pop / total_pop * 100) if total_pop > 0 else 0
        male_ratio = (target_male_pop / total_pop * 100) if total_pop > 0 else 0
        female_ratio = (target_female_pop / total_pop * 100) if total_pop > 0 else 0
        
        st.subheader(f"📊 {row['시도']} {row['시군구']} ({st.session_state.selected_year}년) {curr_age_group} 인구 분석")
        
        # 지표 출력
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("총 인구수", f"{total_pop:,} 명")
        m_col2.metric(f"{curr_age_group} 총 인구수", f"{target_total_pop:,} 명 ({target_ratio:.1f}%)")
        m_col3.metric(f"남성 {curr_age_group} 인구수", f"{target_male_pop:,} 명 ({male_ratio:.1f}%)")
        m_col4.metric(f"여성 {curr_age_group} 인구수", f"{target_female_pop:,} 명 ({female_ratio:.1f}%)")
        
        # 성별 분리 픽토그램 시각화 (아이콘 1개 = 0.5%)
        st.write(f"#### 👦👧 {curr_age_group} 성별 인구 비율 픽토그램 (아이콘 1개 = 0.5%)")
        
        male_icons = int(round(male_ratio * 2))
        female_icons = int(round(female_ratio * 2))
        
        pic_col1, pic_col2 = st.columns(2)
        
        with pic_col1:
            st.markdown(f"**👦 남성 {curr_age_group} 비율 ({male_ratio:.1f}%)**")
            male_html = "<div style='font-size: 22px; line-height: 1.5; background-color: #eef6ff; padding: 12px; border-radius: 8px;'>"
            for i in range(1, 41):
                if i <= male_icons:
                    male_html += "👦 "
                else:
                    male_html += "<span style='opacity: 0.15;'>⚪</span> "
                if i % 10 == 0:
                    male_html += "<br>"
            male_html += "</div>"
            st.components.v1.html(male_html, height=180)

        with pic_col2:
            st.markdown(f"**👧 여성 {curr_age_group} 비율 ({female_ratio:.1f}%)**")
            female_html = "<div style='font-size: 22px; line-height: 1.5; background-color: #fdeef4; padding: 12px; border-radius: 8px;'>"
            for i in range(1, 41):
                if i <= female_icons:
                    female_html += "👧 "
                else:
                    female_html += "<span style='opacity: 0.15;'>⚪</span> "
                if i % 10 == 0:
                    female_html += "<br>"
            female_html += "</div>"
            st.components.v1.html(female_html, height=180)
            
        # [상세보기] 메뉴 클릭 시 세부 연령별 인구 그래프 제공
        with st.expander(f"🔍 [상세보기] {curr_age_group} 세부 연령별·성별 인구 그래프 보기"):
            if curr_age_group == "70대 이상":
                age_range_list = list(range(70, 80))
            else:
                start_age = int(curr_age_group.replace("대", ""))
                age_range_list = list(range(start_age, start_age + 10))
                
            ages = [f"{a}세" for a in age_range_list]
            male_counts = [row.get(f'남_{a}세', 0) for a in age_range_list]
            female_counts = [row.get(f'여_{a}세', 0) for a in age_range_list]
            
            df_detail = pd.DataFrame({
                '연령': ages + ages,
                '인구수': male_counts + female_counts,
                '성별': ['남성'] * len(ages) + ['여성'] * len(ages)
            })
            
            fig_detail = px.bar(
                df_detail, 
                x='연령', 
                y='인구수', 
                color='성별', 
                barmode='group',
                title=f"{row['시도']} {row['시군구']} {curr_age_group} 세부 연령별 인구 분포",
                color_discrete_map={'남성': '#2b5c8f', '여성': '#d95f87'},
                text_auto=',d'
            )
            
            fig_detail.update_layout(
                xaxis_title="연령",
                yaxis_title="인구수(명)",
                legend_title="성별",
                margin=dict(l=20, r=20, t=50, b=20)
            )
            
            st.plotly_chart(fig_detail, use_container_width=True)

elif st.session_state.selected_sido != "전체":
    st.info(f"👉 위의 드롭다운에서 **[{st.session_state.selected_sido}]** 내의 **시·군·구**를 선택하시면 선택하신 **{curr_age_group}** 성별 인구 픽토그램과 세부 그래프를 확인하실 수 있습니다.")
else:
    st.info(f"👉 지도 하단의 드롭다운에서 **시·도** 및 **시·군·구**를 선택하시면 해당 지역으로 확대되며 **{curr_age_group}** 상세 인구 분석 정보를 확인하실 수 있습니다.")
