import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

# 1. 페이지 기본 설정 (넓은 화면 레이아웃)
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    page_icon="🗺️",
    layout="wide"
)

# 2. 데이터 로딩 함수 (캐싱을 통한 속도 향상)
@st.cache_data
def load_population_data():
    """인구 데이터(CSV.GZ)를 읽어와 시군구별 고령화율을 계산합니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # 코드는 앞자리의 '0'이 사라지지 않도록 반드시 str(문자열) 타입으로 읽어옵니다.
    df = pd.read_csv(url, compression='gzip', dtype={'코드': str})
    
    # 가장 최신 연도 데이터만 필터링
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 행정동 코드(10자리)의 앞 5자리를 잘라 시군구 코드로 생성
    df_latest['sigungu_code'] = df_latest['코드'].str.slice(0, 5)
    
    # '계_'로 시작하는 나이별 열 이름 자동 찾기
    total_pop_cols = [col for col in df_latest.columns if col.startswith('계_')]
    
    # 65세 이상에 해당하는 열 선별 ('계_65세' ~ '계_99세', '계_100세 이상')
    elderly_cols = []
    for col in total_pop_cols:
        age_str = col.replace('계_', '').replace('세', '').replace(' 이상', '')
        if age_str.isdigit():
            if int(age_str) >= 65:
                elderly_cols.append(col)
        elif col == '계_100세 이상':
            elderly_cols.append(col)
            
    # 시군구 단위로 총 인구와 65세 이상 인구 합산
    df_latest['total_pop'] = df_latest[total_pop_cols].sum(axis=1)
    df_latest['elderly_pop'] = df_latest[elderly_cols].sum(axis=1)
    
    # 시군구 코드 기준으로 데이터 집계
    grouped = df_latest.groupby('sigungu_code').agg({
        '시도': 'first',
        '시군구': 'first',
        'total_pop': 'sum',
        'elderly_pop': 'sum'
    }).reset_index()
    
    # 고령화율(%) 계산 (소수점 첫째 자리까지)
    grouped['elderly_ratio'] = (grouped['elderly_pop'] / grouped['total_pop'] * 100).round(1)
    
    return grouped, latest_year

@st.cache_data
def load_geojson():
    """전국 시군구 경계 GeoJSON 데이터를 불러옵니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(url)
    return response.json()

# 3. 앱 화면 구성
st.title("🗺️ 전국 시군구 고령화 비율 지도")

# 데이터 불러오기
with st.spinner("데이터를 로딩 중입니다... 잠시만 기다려 주세요."):
    df_sigungu, latest_year = load_population_data()
    geojson_data = load_geojson()

st.caption(f"기준 연도: **{latest_year}년** (데이터 출처: 모두의데이터)")

# 4. 고령화율 5단계 범류화 (19%, 23%, 28%, 38% 기준)
bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_sigungu['ratio_group'] = pd.cut(
    df_sigungu['elderly_ratio'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# 5단계 구분을 위한 색상 팔레트 (옅은 노랑/연두 -> 진한 붉은색)
color_discrete_map = {
    '19% 미만': '#fef0d9',
    '19% 이상 ~ 23% 미만': '#fdd49e',
    '23% 이상 ~ 28% 미만': '#fdbb84',
    '28% 이상 ~ 38% 미만': '#fc8d59',
    '38% 이상': '#d7301f'
}

# 5. Plotly 단계구분도(Choropleth) 지도 생성
fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_data,
    locations='sigungu_code',         # 데이터의 시군구 코드
    featureidkey="properties.코드",    # GeoJSON의 5자리 시군구 코드
    color='ratio_group',              # 범주형 구간 색상 적용
    color_discrete_map=color_discrete_map,
    category_orders={'ratio_group': labels},  # 범례 순서 정렬
    center={"lat": 35.8, "lon": 127.8},       # 지도 중앙 위치 (대한민국 중심)
    zoom=6.2,                                 # 초기 확대 비율
    hover_name='시군구',
    hover_data={
        '시도': True,
        'elderly_ratio': ':.1f%',
        'sigungu_code': False,
        'ratio_group': False
    },
    labels={
        'elderly_ratio': '고령화율',
        'ratio_group': '고령화 비율 구간'
    }
)

# 지도 스타일 변경: 배경 타일 제거, 경계선 설정
fig.update_layout(
    mapbox_style="white-bg",                  # 배경 타일 없음
    mapbox_layers=[{
        "below": 'traces',
        "sourcetype": "raster",
        "source": ["data:image/png;base64,iVBORw0KGgoAAAANSU50EUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="]
    }],
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    legend=dict(
        title=dict(text="<b>고령화율 구간</b>"),
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.02,
        bgcolor="rgba(255, 255, 255, 0.8)"
    )
)

fig.update_traces(
    marker_line_width=0.5,
    marker_line_color="#444444"              # 경계선 색상
)

# 스트림릿 화면에 지도 출력
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 6. 상위 10개 / 하위 10개 시군구 데이터표 생성
col1, col2 = st.columns(2)

# 정렬 및 표에 표시할 열 구성
display_cols = ['시도', '시군구', 'elderly_ratio', 'total_pop', 'elderly_pop']
column_names = {'시도': '시도', '시군구': '시군구', 'elderly_ratio': '고령화율(%)', 'total_pop': '총인구(명)', 'elderly_pop': '65세 이상 인구(명)'}

# 고령화율 높은 순 상위 10개
top10 = df_sigungu.sort_values(by='elderly_ratio', ascending=False).head(10)[display_cols]
top10 = top10.rename(columns=column_names).reset_index(drop=True)

# 고령화율 낮은 순 하위 10개
bottom10 = df_sigungu.sort_values(by='elderly_ratio', ascending=True).head(10)[display_cols]
bottom10 = bottom10.rename(columns=column_names).reset_index(drop=True)

with col1:
    st.subheader("🔴 고령화율 상위 10개 지역")
    st.dataframe(top10, use_container_width=True)

with col2:
    st.subheader("🔵 고령화율 하위 10개 지역")
    st.dataframe(bottom10, use_container_width=True)
