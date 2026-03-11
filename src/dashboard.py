import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import os
import ast
import sys

# 데이터베이스 경로 설정 (GitHub 업로드 경로 기준 상대 경로)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'data', 'nemostore.db')

# 컬럼명 한글 매핑
COLUMN_MAPPING = {
    'title': '매물명',
    'businessMiddleCodeName': '업종',
    'deposit': '보증금(만원)',
    'monthlyRent': '월세(만원)',
    'premium': '권리금(만원)',
    'maintenanceFee': '관리비(만원)',
    'size_m2': '면적(㎡)',
    'size_py': '면적(평)',
    'floor': '층수',
    'nearSubwayStation': '주변역',
    'viewCount': '조회수',
    'favoriteCount': '관심수',
    'createdDateUtc': '등록일'
}

@st.cache_data
def load_data():
    if not os.path.exists(DB_PATH):
        # 만약 data 폴더가 루트에 있는 경우 대응
        alt_path = os.path.join(BASE_DIR, 'data', 'nemostore.db')
        target_path = DB_PATH if os.path.exists(DB_PATH) else alt_path
        if not os.path.exists(target_path):
            st.error(f"데이터베이스 파일을 찾을 수 없습니다: {DB_PATH}")
            return pd.DataFrame()
        path_to_use = target_path
    else:
        path_to_use = DB_PATH

    conn = sqlite3.connect(path_to_use)
    try:
        df = pd.read_sql_query("SELECT * FROM items", conn)
    except:
        return pd.DataFrame()
    finally:
        conn.close()

    # 데이터 전처리
    num_cols = ['deposit', 'monthlyRent', 'premium', 'maintenanceFee', 'viewCount', 'favoriteCount']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if 'size' in df.columns:
        df['size_m2'] = df['size']
        df['size_py'] = (df['size'] / 3.3058).round(1)

    def parse_url_list(x):
        try:
            if isinstance(x, str) and x.startswith('['):
                return ast.literal_eval(x)
            return [x] if x else []
        except:
            return []

    df['small_images'] = df['smallPhotoUrls'].apply(parse_url_list)
    df['origin_images'] = df['originPhotoUrls'].apply(parse_url_list)
    df['lat'] = 37.528 + (df.index % 100) * 0.0001
    df['lon'] = 126.917 + (df.index % 100) * 0.0001
    df['category'] = df['businessMiddleCodeName'].fillna('기타')

    return df

def get_benchmarks(df):
    benchmarks = df.groupby('category').agg({
        'deposit': 'mean',
        'monthlyRent': 'mean',
        'premium': 'mean',
        'size_m2': 'mean'
    }).reset_index()
    benchmarks.columns = ['category', 'avg_deposit', 'avg_rent', 'avg_premium', 'avg_size']
    return benchmarks

def filter_data(df, search_term="", selected_categories=None, 
                deposit_range=(0, 200000), rent_range=(0, 22000), 
                premium_range=(0, 1000000), size_range=(0.0, 700.0)):
    filtered_df = df.copy()
    if search_term:
        filtered_df = filtered_df[
            filtered_df['title'].str.contains(search_term, case=False, na=False) |
            filtered_df['category'].str.contains(search_term, case=False, na=False)
        ]
    if selected_categories:
        filtered_df = filtered_df[filtered_df['category'].isin(selected_categories)]
    filtered_df = filtered_df[
        (filtered_df['deposit'] >= deposit_range[0]) & (filtered_df['deposit'] <= deposit_range[1]) &
        (filtered_df['monthlyRent'] >= rent_range[0]) & (filtered_df['monthlyRent'] <= rent_range[1]) &
        (filtered_df['premium'] >= premium_range[0]) & (filtered_df['premium'] <= premium_range[1]) &
        (filtered_df['size_m2'] >= size_range[0]) & (filtered_df['size_m2'] <= size_range[1])
    ]
    return filtered_df
import math

# 페이지 설정
st.set_page_config(
    page_title="Nemostore Pro 대시보드 V2",
    page_icon="🏢",
    layout="wide"
)

# 자바스크립트/CSS를 이용한 스타일 개선 (상세 페이지 느낌을 주기 위함)
st.markdown("""
<style>
    .item-card {
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #f0f2f6;
        transition: 0.3s;
        background-color: white;
        min-height: 450px;
        margin-bottom: 20px;
    }
    .item-card:hover {
        box-shadow: 0 10px 15px rgba(0,0,0,0.05);
        border-color: #d1d5db;
    }
    .card-title {
        font-weight: bold;
        font-size: 1.05em;
        line-height: 1.4;
        height: 2.8em;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin: 10px 0;
    }
    .benchmark-pos { color: #ff4b4b; font-weight: bold; }
    .benchmark-neg { color: #00875a; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 데이터 로드
df = load_data()
benchmarks = get_benchmarks(df)

# 세션 상태 초기화
if 'selected_item_id' not in st.session_state:
    st.session_state.selected_item_id = None
if 'img_index' not in st.session_state:
    st.session_state.img_index = 0

def select_item(item_id):
    st.session_state.selected_item_id = item_id
    st.session_state.img_index = 0 # 초기화

# --- 사이드바 ---
st.sidebar.header("🎯 필터 컨트롤")

if st.sidebar.button("🏠 홈으로 (목록 초기화)"):
    st.session_state.selected_item_id = None
    st.rerun()

search_term = st.sidebar.text_input("매물명/키워드 검색", "")

# 업종 필터
categories = sorted(df['category'].unique().tolist())
selected_categories = st.sidebar.multiselect("업종 필터", categories, default=[])

# 가격 필터
deposit_range = st.sidebar.slider("보증금(만원)", 0, int(df['deposit'].max()), (0, int(df['deposit'].max())))
rent_range = st.sidebar.slider("월세(만원)", 0, int(df['monthlyRent'].max()), (0, int(df['monthlyRent'].max())))
premium_range = st.sidebar.slider("권리금(만원)", 0, int(df['premium'].max()), (0, int(df['premium'].max())))
size_range = st.sidebar.slider("전용면적(㎡)", 0.0, float(df['size_m2'].max()), (0.0, float(df['size_m2'].max())))

# 필터링 적용
filtered_df = filter_data(df, search_term, selected_categories, deposit_range, rent_range, premium_range, size_range)

# --- 메인 화면 로직 분기 ---
if st.session_state.selected_item_id:
    # --- 상세 페이지 화면 ---
    item = df[df['id'] == st.session_state.selected_item_id].iloc[0]
    
    col_back, _ = st.columns([1, 10])
    if col_back.button("⬅️ 뒤로가기"):
        st.session_state.selected_item_id = None
        st.rerun()

    st.title(f"🏢 {item['title']}")
    
    col_img, col_info = st.columns([1.5, 1])
    
    with col_img:
        # 사진 페이지네이션 구현
        images = item['origin_images']
        if images:
            num_images = len(images)
            idx = st.session_state.img_index
            
            st.image(images[idx], use_container_width=True)
            
            # 페이지네이션 버튼
            btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
            if btn_col1.button("◀️ 이전", disabled=(idx == 0)):
                st.session_state.img_index -= 1
                st.rerun()
            
            btn_col2.markdown(f"<div style='text-align: center; font-weight: bold;'>{idx + 1} / {num_images}</div>", unsafe_allow_html=True)
            
            if btn_col3.button("다음 ▶️", disabled=(idx == num_images - 1)):
                st.session_state.img_index += 1
                st.rerun()
        else:
            st.image(item['previewPhotoUrl'], use_container_width=True)
            
    with col_info:
        st.subheader("📌 매물 정보")
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.write(f"**업종:** {item['category']}")
            st.write(f"**층수:** {item['floor']}층")
            st.write(f"**면적:** {item['size_m2']}㎡ ({item['size_py']}평)")
        with info_col2:
            st.write(f"**보증금:** {item['deposit']:,.0f} 만원")
            st.write(f"**월세:** {item['monthlyRent']:,.0f} 만원")
            st.write(f"**권리금:** {item['premium']:,.0f} 만원")
            
        st.divider()
        
        # 벤치마킹
        st.subheader("⚖️ 시장 가치 비교 (Benchmarking)")
        cat_avg = benchmarks[benchmarks['category'] == item['category']].iloc[0]
        
        metrics = [
            ("월세", item['monthlyRent'], cat_avg['avg_rent']),
            ("보증금", item['deposit'], cat_avg['avg_deposit']),
            ("권리금", item['premium'], cat_avg['avg_premium'])
        ]
        
        for name, val, avg in metrics:
            diff_pct = ((val - avg) / avg * 100) if avg > 0 else 0
            color = "benchmark-pos" if diff_pct > 0 else "benchmark-neg"
            trend = "높음" if diff_pct > 0 else "낮음"
            st.markdown(f"{name}: **{val:,.0f}만원** (업종 평균 대비 <span class='{color}'>{abs(diff_pct):.1f}% {trend}</span>)", unsafe_allow_html=True)

        st.divider()
        st.write(f"**주변역:** {item['nearSubwayStation']}")
        st.write(f"**조회수:** {item['viewCount']}")
        
        # 지도 (상세 위치)
        st.subheader("🗺️ 위치 정보")
        st.map(pd.DataFrame({'lat': [item['lat']], 'lon': [item['lon']]}))

else:
    # --- 메인 대시보드 화면 ---
    tab_gallery, tab_map, tab_analytics, tab_raw = st.tabs(["🖼️ 이미지 갤러리", "📍 지도 보기", "📊 시장 분석 히트맵", "📋 상세 리스트"])

    with tab_gallery:
        st.subheader(f"🏠 매물 탐색 (검색 결과: {len(filtered_df)}건)")
        
        # 격자 형태의 갤러리 구현 (4개씩 한 줄)
        cols = st.columns(4)
        for i, (idx, row) in enumerate(filtered_df.iterrows()):
            with cols[i % 4]:
                # 단일 마운트 포인트로 HTML 구성 (이미지 포함)
                card_html = f"""
                <div class="item-card">
                    <img src="{row['previewPhotoUrl']}" style="width:100%; border-radius:5px; height:180px; object-fit:cover;">
                    <div class="card-title">{row['title']}</div>
                    <div style="font-size: 0.9em; color: #666;">
                        🏷️ {row['deposit']:,.0f}/{row['monthlyRent']:,.0f} (만)<br>
                        📐 {row['size_m2']}㎡ ({row['size_py']}평)<br>
                        🚇 {row['nearSubwayStation']}
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                # 버튼은 Streamlit 기본 버튼 사용 (상호작용을 위해)
                if st.button("상세보기", key=f"btn_{row['id']}", use_container_width=True):
                    select_item(row['id'])
                    st.rerun()

    with tab_map:
        st.subheader("📍 매물 위치 및 밀집도")
        if not filtered_df.empty:
            # 밀집도 시각화 (Scatter Mapbox)
            fig_map = px.scatter_mapbox(filtered_df, lat="lat", lon="lon", 
                                       color="monthlyRent", size="size_m2",
                                       hover_name="title", hover_data=["category", "deposit"],
                                       color_continuous_scale=px.colors.cyclical.IceFire, 
                                       size_max=15, zoom=13,
                                       mapbox_style="carto-positron",
                                       title="지도 기반 매물 분포 (색상: 월세, 크기: 면적)")
            st.plotly_chart(fig_map, use_container_width=True)
        else:
            st.warning("표시할 수 있는 매물이 없습니다.")

    with tab_analytics:
        st.subheader("📊 층별 및 업종별 심층 분석")
        col_an1, col_an2 = st.columns(2)
        
        with col_an1:
            # 층별 임대료 분석
            floor_rent = filtered_df.groupby('floor')['monthlyRent'].mean().reset_index()
            fig_floor = px.bar(floor_rent, x='floor', y='monthlyRent', 
                              title='🏢 층별 평균 월세 비교',
                              labels={'floor': '층수', 'monthlyRent': '평균 월세(만원)'},
                              color='monthlyRent', color_continuous_scale='Reds')
            st.plotly_chart(fig_floor, use_container_width=True)
            
        with col_an2:
            # 면적당 권리금 분석 (효율성 지표)
            filtered_df['premium_per_size'] = filtered_df['premium'] / filtered_df['size_m2']
            fig_eff = px.box(filtered_df, x='category', y='premium_per_size',
                            title='📉 업종별 단위 면적당 권리금 분포',
                            labels={'category': '업종', 'premium_per_size': '단위 면적당 권리금(만원/㎡)'},
                            color='category')
            st.plotly_chart(fig_eff, use_container_width=True)

    with tab_raw:
        st.subheader("📋 전체 매물 상세 리스트")
        # 컬럼명 한글화 적용
        display_df = filtered_df.rename(columns=COLUMN_MAPPING)
        selected_cols = [COLUMN_MAPPING[k] for k in COLUMN_MAPPING.keys() if k in filtered_df.columns]
        st.dataframe(display_df[selected_cols], use_container_width=True)
