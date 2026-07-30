import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="전국 고령화 & 연령구간별 인구 탐색기",
    page_icon="🗺️",
    layout="wide"
)

# 2. 데이터 로딩 함수 (전체 연도 및 전체 연령 데이터 가공)
@st.cache_data
def load_full_population_data():
    """전체 연도의 인구 데이터를 불러와 연령대 및 고령/비고령 인구를 집계합니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    df = pd.read_csv(url, compression='gzip', dtype={'코드': str})
    df['sigungu_code'] = df['코드'].str.slice(0, 5)
    
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
            
    df['total_pop'] = df[total_pop_cols].sum(axis=1)
    df['elderly_pop'] = df[elderly_cols].sum(axis=1)
    df['other_pop'] = df['total_pop'] - df['elderly_pop']
    
    # 연령 구간 정의
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
    
    agg_dict = {
        '시도': 'first',
        '시군구': 'first',
        'total_pop': 'sum',
        'elderly_pop': 'sum',
        'other_pop': 'sum'
    }
    
    for group_name in age_groups.keys():
        agg_dict[f'{group_name}_total_pop'] = 'sum'
        agg_dict[f'{group_name}_남_pop'] = 'sum'
        agg_dict[f'{group_name}_여_pop'] = 'sum'
        
    for age in range(0, 100):
        if f'계_{age}세' in df.columns: agg_dict[f'계_{age}세'] = 'sum'
        if f'남_{age}세' in df.columns: agg_dict[f'남_{age}세'] = 'sum'
        if f'여_{age}세' in df.columns: agg_dict[f'여_{age}세'] = 'sum'
    
    grouped = df.groupby(['연도', 'sigungu_code']).agg(agg_dict).reset_index()
    grouped['elderly_ratio'] = (grouped['elderly_pop'] / grouped['total_pop'] * 100).round(1)
    grouped['other_ratio'] = (100.0 - grouped['elderly_ratio']).round(1)
    
    return grouped

@st.cache_data
def load_geojson():
    """전국 시군구 경계 GeoJSON 데이터를 불러옵니다."""
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

# 데이터 로드
with st.spinner("전국 인구 데이터를 불러오는 중..."):
    df_pop = load_full_population_data()
    geojson_data = load_geojson()

# GeoJSON 데이터에서 사용 가능한 시군구 코드 집합 추출
geojson_codes = set()
if geojson_data and 'features' in geojson_data:
    for feature in geojson_data['features']:
        code = feature.get('properties', {}).get('코드')
        if code:
            geojson_codes.add(str(code))

# GeoJSON 코드와 매칭되는 인구 데이터 필터링
valid_df = df_pop[df_pop['sigungu_code'].astype(str).isin(geojson_codes)]
valid_sido_list = sorted(list(valid_df['시도'].dropna().unique()))

# 세션 상태 초기화
if 'selected_sido' not in st.session_state or st.session_state.selected_sido not in (["전체"] + valid_sido_list):
    st.session_state.selected_sido = "전체"
if 'selected_sigungu' not in st.session_state:
    st.session_state.selected_sigungu = "전체"
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = int(df_pop['연도'].max())
if 'selected_age_group' not in st.session_state:
    st.session_state.selected_age_group = "10대"

# --- [메인 화면 구성] ---
st.title("🗺️ 전국 시군구 고령화 지도 & 연령대별 인구 탐색기")

sido_centers = {
    "전체": {"lat": 35.8, "lon": 127.8, "zoom": 6.2},
    "서울특별시": {"lat": 37.5665, "lon": 126.9780, "zoom": 9.5},
    "부산광역시": {"lat": 35.1796, "lon": 129.0756, "zoom": 9.5},
    "대구광역시": {"lat": 35.8714, "lon": 128.6014, "zoom": 9.0},
    "인천광역시": {"lat": 37.4563, "lon": 126.7052, "zoom": 9.0},
    "광주광역시": {"lat": 35.1595, "lon": 126.8526, "zoom": 10.0},
    "대전광역시": {"lat": 36.3504, "lon": 127.3845, "zoom": 10.0},
    "울산광역시": {"lat": 35.5384, "lon": 129.3114, "zoom": 9.8},
    "경기도": {"lat": 37.4138, "lon": 127.5183, "zoom": 8.2},
    "충청북도": {"lat": 36.6357, "lon": 127.4912, "zoom": 8.2},
    "충청남도": {"lat": 36.5184, "lon": 126.8000, "zoom": 8.3},
    "전라남도": {"lat": 34.8161, "lon": 126.4629, "zoom": 8.0},
    "경상북도": {"lat": 36.5760, "lon": 128.5056, "zoom": 7.8},
    "경상남도": {"lat": 35.4606, "lon": 128.2132, "zoom": 8.2},
    "제주특별자치도": {"lat": 33.4890, "lon": 126.4983, "zoom": 9.2}
}

view_config = sido_centers.get(st.session_state.selected_sido, sido_centers["전체"])
df_current_year = valid_df[valid_df['연도'] == st.session_state.selected_year].copy()

bins = [0, 19, 23, 28, 38, 100]
labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']

df_current_year['ratio_group'] = pd.cut(
    df_current_year['elderly_ratio'], 
    bins=bins, 
    labels=labels, 
    right=False
)

green_color_discrete_map = {
    '19% 미만': '#edf8e9',
    '19% 이상 ~ 23% 미만': '#bae4b3',
    '23% 이상 ~ 28% 미만': '#74c476',
    '28% 이상 ~ 38% 미만': '#31a354',
    '38% 이상': '#006d2c'
}

if st.session_state.selected_sido != "전체":
    map_data = df_current_year[df_current_year['시도'] == st.session_state.selected_sido]
else:
    map_data = df_current_year

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

fig.update_layout(
    mapbox_style="white-bg",
    mapbox_layers=[{
        "below": 'traces',
        "sourcetype": "raster",
        "source": ["data:image/png;base64,iVBORw0KGgoAAAANSU50EUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORUS5CYII="]
    }],
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    transition_duration=3000,
    legend=dict(
        title=dict(text="<b>고령화율 구간</b>", font=dict(color="#000000", size=13)),
        font=dict(color="#000000", size=12),
        yanchor="top", y=0.98, xanchor="left", x=0.02,
        bgcolor="rgba(255, 255, 255, 0.9)"
    )
)

fig.update_traces(
    marker_line_width=0.8,
    marker_line_color="#222222"
)

st.plotly_chart(fig, use_container_width=True)


# --- [지도 하단 선택 드롭다운 UI] ---
st.markdown("### 📍 지역, 연도 및 연령대 선택 옵션")

col_sido, col_sigungu, col_year, col_age = st.columns(4)

with col_sido:
    sido_options = ["전체"] + valid_sido_list
    selected_sido = st.selectbox(
        "시·도 선택", 
        sido_options, 
        index=sido_options.index(st.session_state.selected_sido)
    )
    if selected_sido != st.session_state.selected_sido:
        st.session_state.selected_sido = selected_sido
        st.session_state.selected_sigungu = "전체"
        st.rerun()

with col_sigungu:
    if st.session_state.selected_sido != "전체":
        available_sigungu = ["전체"] + sorted(list(valid_df[valid_df['시도'] == st.session_state.selected_sido]['시군구'].dropna().unique()))
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

# --- [상세 인구 분석 및 결과 표시] ---
curr_age_group = st.session_state.selected_age_group

if st.session_state.selected_sido != "전체" and st.session_state.selected_sigungu != "전체":
    target_data = valid_df[
        (valid_df['시도'] == st.session_state.selected_sido) & 
        (valid_df['시군구'] == st.session_state.selected_sigungu) & 
        (valid_df['연도'] == st.session_state.selected_year)
    ]
    
    if not target_data.empty:
        row = target_data.iloc[0]
        total_pop = int(row['total_pop'])
        elderly_pop = int(row['elderly_pop'])
        other_pop = int(row['other_pop'])
        elderly_ratio = row['elderly_ratio']
        other_ratio = row['other_ratio']

        target_total_pop = int(row[f'{curr_age_group}_total_pop'])
        target_male_pop = int(row[f'{curr_age_group}_남_pop'])
        target_female_pop = int(row[f'{curr_age_group}_여_pop'])
        
        target_ratio = (target_total_pop / total_pop * 100) if total_pop > 0 else 0
        male_ratio = (target_male_pop / total_pop * 100) if total_pop > 0 else 0
        female_ratio = (target_female_pop / total_pop * 100) if total_pop > 0 else 0
        
        # 1. 지표 요약 (Metric)
        st.subheader(f"📊 {row['시도']} {row['시군구']} ({st.session_state.selected_year}년) 인구 분석")
        
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("전체 인구수", f"{total_pop:,} 명")
        m_col2.metric(f"{curr_age_group} 인구수", f"{target_total_pop:,} 명 ({target_ratio:.1f}%)")
        m_col3.metric("👴 65세 이상 고령인구", f"{elderly_pop:,} 명 ({elderly_ratio:.1f}%)")
        m_col4.metric("🧑 65세 미만 그 외 인구", f"{other_pop:,} 명 ({other_ratio:.1f}%)")
        
        # 2. 고령화 단계 판정 및 익살스러운 애니메이션 배지
        if elderly_ratio >= 20.0:
            status_title = "👵🚨 [초고령사회] 으악! 지팡이 춤판이 벌어졌어요!"
            status_desc = f"고령인구 비율이 무려 {elderly_ratio:.1f}%! 경로당 잔칫날입니다!"
            badge_bg = "#ffebee"
            badge_border = "#ef5350"
            anim_class = "super-old-bounce"
            emoji_main = "👵🕺"
        elif elderly_ratio >= 14.0:
            status_title = "🧓 짚신도 짝이 있는 [고령사회]"
            status_desc = f"고령인구 비율 {elderly_ratio:.1f}%. 어르신들의 돋보기 파워가 느껴집니다!"
            badge_bg = "#fff8e1"
            badge_border = "#ffca28"
            anim_class = "old-shake"
            emoji_main = "🧓👓"
        elif elderly_ratio >= 7.0:
            status_title = "👴 [고령화사회] 은근슬쩍 머리가 희끗희끗!"
            status_desc = f"고령인구 비율 {elderly_ratio:.1f}%. 이제 슬슬 안마의자가 필요해집니다."
            badge_bg = "#f1f8e9"
            badge_border = "#9ccc65"
            anim_class = "mild-wiggle"
            emoji_main = "👴🌱"
        else:
            status_title = "👶⚡ [젊은 도시] 파릇파릇 에너지가 넘쳐나요!"
            status_desc = f"고령인구 비율 {elderly_ratio:.1f}%. 청년들의 댄스 배틀 구역!"
            badge_bg = "#e3f2fd"
            badge_border = "#42a5f5"
            anim_class = "young-jump"
            emoji_main = "🏃⚡"

        anim_css = f"""
        <style>
        @keyframes superBounce {{
            0%, 100% {{ transform: translateY(0) rotate(0deg) scale(1); }}
            25% {{ transform: translateY(-12px) rotate(-8deg) scale(1.08); }}
            50% {{ transform: translateY(0) rotate(8deg) scale(0.95); }}
            75% {{ transform: translateY(-6px) rotate(-4deg) scale(1.03); }}
        }}
        @keyframes oldShake {{
            0%, 100% {{ transform: translateX(0); }}
            20% {{ transform: translateX(-6px) rotate(-3deg); }}
            40% {{ transform: translateX(6px) rotate(3deg); }}
            60% {{ transform: translateX(-4px); }}
            80% {{ transform: translateX(4px); }}
        }}
        @keyframes mildWiggle {{
            0%, 100% {{ transform: rotate(0deg); }}
            50% {{ transform: rotate(5deg) scale(1.04); }}
        }}
        @keyframes youngJump {{
            0%, 100% {{ transform: translateY(0) scale(1); }}
            50% {{ transform: translateY(-16px) scale(1.15); }}
        }}
        
        .super-old-bounce {{ animation: superBounce 1.2s infinite ease-in-out; display: inline-block; }}
        .old-shake {{ animation: oldShake 1.5s infinite ease-in-out; display: inline-block; }}
        .mild-wiggle {{ animation: mildWiggle 2s infinite ease-in-out; display: inline-block; }}
        .young-jump {{ animation: youngJump 0.8s infinite ease-in-out; display: inline-block; }}
        
        .funny-container {{
            background-color: {badge_bg};
            border: 3px solid {badge_border};
            border-radius: 16px;
            padding: 18px;
            text-align: center;
            margin: 15px 0 25px 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        .funny-emoji {{
            font-size: 45px;
            margin-bottom: 8px;
        }}
        .funny-title {{
            font-size: 21px;
            font-weight: bold;
            color: #222222;
            margin-bottom: 4px;
        }}
        .funny-desc {{
            font-size: 14px;
            color: #555555;
        }}
        </style>
        
        <div class="funny-container">
            <div class="funny-emoji {anim_class}">{emoji_main}</div>
            <div class="funny-title">{status_title}</div>
            <div class="funny-desc">{status_desc}</div>
        </div>
        """
        st.components.v1.html(anim_css, height=195)
        
        # 3. 고령인구 vs 그 외 연령 비율 파이차트 & 픽토그램 2열 배치
        c_left, c_right = st.columns(2)
        
        with c_left:
            df_compare_pie = pd.DataFrame({
                '구분': ['65세 이상 고령인구', '65세 미만 그 외 인구'],
                '인구수': [elderly_pop, other_pop]
            })
            fig_pie = px.pie(
                df_compare_pie, 
                names='구분', 
                values='인구수',
                title=f"⚖️ 고령인구 vs 그 외 인구 비율 (%)",
                color='구분',
                color_discrete_map={'65세 이상 고령인구': '#d7301f', '65세 미만 그 외 인구': '#31a354'},
                hole=0.4
            )
            fig_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

        with c_right:
            st.write(f"#### 👦👧 {curr_age_group} 성별 인구 비율 픽토그램")
            male_icons = int(round(male_ratio * 2))
            female_icons = int(round(female_ratio * 2))
            
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                st.markdown(f"**👦 남성 ({male_ratio:.1f}%)**")
                male_html = "<div style='font-size: 18px; line-height: 1.4; background-color: #eef6ff; padding: 10px; border-radius: 8px;'>"
                for i in range(1, 41):
                    male_html += "👦 " if i <= male_icons else "<span style='opacity: 0.15;'>⚪</span> "
                    if i % 10 == 0: male_html += "<br>"
                male_html += "</div>"
                st.components.v1.html(male_html, height=160)

            with p_col2:
                st.markdown(f"**👧 여성 ({female_ratio:.1f}%)**")
                female_html = "<div style='font-size: 18px; line-height: 1.4; background-color: #fdeef4; padding: 10px; border-radius: 8px;'>"
                for i in range(1, 41):
                    female_html += "👧 " if i <= female_icons else "<span style='opacity: 0.15;'>⚪</span> "
                    if i % 10 == 0: female_html += "<br>"
                female_html += "</div>"
                st.components.v1.html(female_html, height=160)

        # 4. 세부 연령별/성별 인구 분포 막대그래프
        with st.expander(f"🔍 [상세보기] {curr_age_group} 세부 연령별·성별 인구 그래프 보기", expanded=True):
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
    st.info(f"👉 위의 드롭다운에서 **[{st.session_state.selected_sido}]** 내의 **시·군·구**를 선택하시면 선택하신 지역의 분석 결과를 확인하실 수 있습니다.")
else:
    st.info("👉 지도 하단의 드롭다운에서 **시·도** 및 **시·군·구**를 선택하시면 해당 지역으로 확대되며 상세 인구 분석 결과를 확인하실 수 있습니다.")
