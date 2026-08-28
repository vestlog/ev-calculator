import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# 페이지 설정
st.set_page_config(page_title="스마트 EV 전비 계산기", page_icon="⚡", layout="wide")

# 아이폰 사파리 키보드 자동 확대 방지 및 모바일 반응형 CSS
st.markdown("""
    <style>
    /* 1. 아이폰 사파리 입력창 터치 시 화면 자동 확대(Zoom-in) 방지 핵심 설정 */
    input, textarea, select, [data-baseweb="input"] input {
        font-size: 16px !important;
    }

    /* 2. 웹페이지 전체 가로 스크롤 차단 */
    html, body {
        max-width: 100vw;
        overflow-x: hidden !important;
    }

    .block-container {
        max-width: 100vw !important;
        overflow-x: hidden !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* 3. 지도 및 요소 가로 넘침 방지 */
    iframe {
        max-width: 100vw !important;
        width: 100% !important;
    }

    [data-testid="stVerticalBlock"] > div {
        max-width: 100% !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ 지능형 전기차 도착 잔량 계산기")
st.markdown("카카오 내비게이션 실시간 경로와 날씨를 연동하여 정확한 잔량을 예측합니다.")

# 1. 전기차 모델 데이터 설정
ev_models = {
    "BMW i4 eDrive40": 80.7,
    "현대 아이오닉5 (롱레인지)": 84.0,
    "기아 EV6 (롱레인지)": 77.4,
    "테슬라 모델3 (롱레인지)": 75.0,
    "테슬라 모델Y (롱레인지)": 75.0
}


# --- API 연동 함수들 ---
def get_address_from_coords(lat, lon):
    try:
        kakao_api_key = st.secrets["KAKAO_API_KEY"]
    except Exception:
        return f"위도: {lat:.4f}, 경도: {lon:.4f}"
    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    params = {"x": lon, "y": lat}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        documents = response.json().get("documents", [])
        if documents:
            address_info = documents[0].get('road_address')
            if address_info:
                return address_info.get('address_name')
            return documents[0].get('address', {}).get('address_name', "주소 확인 불가")
    return f"위도: {lat:.4f}, 경도: {lon:.4f}"


def get_coordinates_from_kakao(query):
    try:
        kakao_api_key = st.secrets["KAKAO_API_KEY"]
    except Exception:
        return None, None, "⚠️ 카카오 API Key 미설정"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}

    url_keyword = "https://dapi.kakao.com/v2/local/search/keyword.json"
    params = {"query": query}
    res_keyword = requests.get(url_keyword, headers=headers, params=params)

    if res_keyword.status_code == 200:
        docs = res_keyword.json().get("documents", [])
        if docs:
            return float(docs[0]['y']), float(docs[0]['x']), f"{docs[0]['place_name']} ({docs[0]['address_name']})"

    url_address = "https://dapi.kakao.com/v2/local/search/address.json"
    res_address = requests.get(url_address, headers=headers, params=params)
    if res_address.status_code == 200:
        docs_addr = res_address.json().get("documents", [])
        if docs_addr:
            return float(docs_addr[0]['y']), float(docs_addr[0]['x']), docs_addr[0]['address_name']

    return None, None, f"'{query}' 검색 결과 없음"


def get_kakao_navi_route(start_lat, start_lon, end_lat, end_lon, priority="RECOMMEND"):
    try:
        kakao_api_key = st.secrets["KAKAO_API_KEY"]
    except Exception:
        return None, None, None, "API Key 미설정"
    url = "https://apis-navi.kakaomobility.com/v1/directions"
    headers = {"Authorization": f"KakaoAK {kakao_api_key}"}
    params = {
        "origin": f"{start_lon},{start_lat}",
        "destination": f"{end_lon},{end_lat}",
        "priority": priority
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        routes = response.json().get("routes", [])
        if routes:
            distance_meters = routes[0]["summary"]["distance"]
            duration_seconds = routes[0]["summary"]["duration"]
            duration_minutes = duration_seconds / 60
            
            path_coords = []
            for section in routes[0].get("sections", []):
                for road in section.get("roads", []):
                    vertexes = road.get("vertexes", [])
                    for i in range(0, len(vertexes), 2):
                        path_coords.append([vertexes[i + 1], vertexes[i]])
            return distance_meters / 1000.0, duration_minutes, path_coords, "성공"
    return None, None, None, "길찾기 실패"


def get_weather(lat, lon):
    try:
        api_key = st.secrets["WEATHER_API_KEY"]
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=kr"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data['main']['temp'], data['weather'][0]['description']
    except Exception:
        pass
    return 20.0, "정보 없음"


# --- UI 레이아웃 시작 ---
with st.sidebar:
    st.header("⚙️ 주행 설정")
    selected_model = st.selectbox("전기차 모델 선택", list(ev_models.keys()))
    capacity = ev_models[selected_model]

    current_soc = st.slider("현재 배터리 잔량 (%)", 0, 100, 80)
    base_efficiency = st.number_input("기준 전비 (km/kWh)", min_value=0.1, value=5.5, step=0.1)

    st.divider()
    st.markdown("📍 **주행 상세 설정**")
    
    # 1. 경로 타입 선택
    route_priority = st.selectbox("경로 우선순위", ["RECOMMEND", "HIGHWAY", "ROAD"], 
                                 format_func=lambda x: {"RECOMMEND": "추천 경로", "HIGHWAY": "고속도로 우선", "ROAD": "국도 우선"}[x])
    
    # 4. 계절 및 차량 설정 온도
    import datetime
    current_month = datetime.date.today().month
    season = "여름" if 6 <= current_month <= 8 else "겨울" if current_month <= 2 or current_month >= 12 else "봄/가을"
    st.info(f"현재 계절: {season}")
    target_temp = st.slider("차량 설정 온도 (°C)", 18, 30, 22)

    st.divider()
    st.markdown("📍 **출발지 설정**")

    # Geolocation 컴포넌트의 버튼을 글씨/텍스트 스타일로 커스텀하기 위한 CSS 주입
    st.markdown("""
        <style>
        /* streamlit_geolocation iframe 내부의 버튼 스타일 제어 시도 및 상위 레이아웃 보완 */
        div[data-testid="stMarkdownContainer"] + div iframe {
            border: none !important;
        }
        /* 현재 위치 파악 텍스트 안내 추가 */
        .gps-label {
            font-size: 14px;
            color: #0068C9;
            font-weight: bold;
            margin-bottom: 5px;
            display: inline-block;
        }
        </style>
        <span class="gps-label">📲 아래 [Get Location] 버튼을 클릭해 현재 위치를 파악하세요:</span>
    """, unsafe_allow_html=True)

    loc = streamlit_geolocation()
    manual_start = st.text_input("출발지 직접 입력 (GPS 미작동 시)", value="")

    start_lat, start_lon = 37.5665, 126.9780
    start_address_name = "서울시청 (기본값)"

    if loc and loc.get('latitude') and loc.get('longitude'):
        start_lat, start_lon = loc['latitude'], loc['longitude']
        start_address_name = get_address_from_coords(start_lat, start_lon)
        st.success(f"📍 파악된 현재 위치: {start_address_name}")
    elif manual_start.strip() != "":
        s_lat, s_lon, s_status = get_coordinates_from_kakao(manual_start)
        if s_lat:
            start_lat, start_lon = s_lat, s_lon
            start_address_name = s_status
            st.info(f"입력된 출발지: {start_address_name}")

    st.divider()
    st.markdown("📍 **도착지 설정**")
    
    # 세션 상태로 검색 결과 캐싱하여 불필요한 반복 호출 방지 및 로딩 흐름 제어
    if "dest_search_query" not in st.session_state:
        st.session_state.dest_search_query = "투윤커피"
    if "dest_lat" not in st.session_state:
        st.session_state.dest_lat = None
    if "dest_lon" not in st.session_state:
        st.session_state.dest_lon = None
    if "dest_status" not in st.session_state:
        st.session_state.dest_status = "도착지 미확인"

    destination_address = st.text_input("도착지 (상호명 또는 주소)", value=st.session_state.dest_search_query)
    
    # 도착지 검색 버튼
    if st.button("🔍 도착지 검색", use_container_width=True) or st.session_state.dest_lat is None:
        st.session_state.dest_search_query = destination_address
        with st.spinner("🔄 주소지를 검색 중입니다..."):
            d_lat, d_lon, d_status = get_coordinates_from_kakao(destination_address)
            st.session_state.dest_lat = d_lat
            st.session_state.dest_lon = d_lon
            st.session_state.dest_status = d_status
            if d_lat:
                st.toast(f"✅ 검색 완료: {d_status}")
            else:
                st.error(f"❌ 검색 실패: {d_status}")

    end_lat = st.session_state.dest_lat
    end_lon = st.session_state.dest_lon
    end_status = st.session_state.dest_status

# --- 백그라운드 데이터 처리 ---
start_temp, start_desc = get_weather(start_lat, start_lon)

if end_lat:
    end_temp, end_desc = get_weather(end_lat, end_lon)
    # 경로 우선순위 반영
    with st.spinner("🛣️ 실시간 경로를 분석 중입니다..."):
        road_distance, travel_time, path_coords, navi_status = get_kakao_navi_route(start_lat, start_lon, end_lat, end_lon, priority=route_priority)
else:
    end_temp, end_desc = (None, None)
    road_distance, travel_time, path_coords, navi_status = (None, None, None, "도착지 미확인")

# --- 메인 대시보드 (날씨 및 지도) ---
st.subheader("🌍 실시간 환경 대시보드")

col1, col2 = st.columns(2)
with col1:
    st.info(f"**출발지 (현재 위치)**\n\n{start_address_name}")
    st.metric(label="현재 기온", value=f"{start_temp}°C", delta=start_desc, delta_color="normal")

with col2:
    if end_lat:
        st.success(f"**도착지 (목적지)**\n\n{end_status}")
        st.metric(label="목적지 기온", value=f"{end_temp}°C", delta=end_desc, delta_color="normal")
    else:
        st.error("도착지 검색 실패. 정확한 상호명/주소를 입력하세요.")

# Folium 지도 렌더링 (반응형 적용)
if end_lat:
    center_lat = (start_lat + end_lat) / 2
    center_lon = (start_lon + end_lon) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

    folium.Marker([start_lat, start_lon], tooltip="출발", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker([end_lat, end_lon], tooltip="도착", icon=folium.Icon(color="red", icon="flag")).add_to(m)

    if path_coords:
        folium.PolyLine(
            locations=path_coords,
            color="#0068C9",
            weight=5,
            opacity=0.8
        ).add_to(m)
        m.fit_bounds(m.get_bounds())
    else:
        folium.PolyLine(locations=[[start_lat, start_lon], [end_lat, end_lon]], color="gray", dash_array="10").add_to(m)

    # height를 380 정도로 조정하여 모바일 세로 화면에서도 한눈에 들어오게 설정
    st_folium(m, use_container_width=True, height=380, returned_objects=[])

st.divider()

# --- 경로 및 잔량 계산 ---
if st.button("🚀 경로 분석 및 배터리 잔량 계산하기", use_container_width=True):
    if not end_lat:
        st.error("도착지를 먼저 정확히 설정해 주세요.")
    elif road_distance is None:
        st.error(f"❌ 경로를 찾을 수 없습니다. ({navi_status})")
    else:
        # 전비 보정 (온도/계절 + 교통 + 경로)
        adjusted_efficiency = base_efficiency
        
        # 1. 온도/계절 보정 (간단 모델)
        temp_diff = abs(target_temp - end_temp)
        if season == "겨울":
            # 겨울엔 기온 낮으면 큰 페널티
            penalty = (max(0, 20 - end_temp)) * 0.02 + (temp_diff * 0.005)
            adjusted_efficiency *= (1 - penalty)
        elif season == "여름":
            # 여름엔 기온 높으면 페널티
            penalty = (max(0, end_temp - 25)) * 0.01 + (temp_diff * 0.003)
            adjusted_efficiency *= (1 - penalty)
        
        # 2. 교통 보정
        avg_speed = road_distance / (travel_time / 60) if travel_time > 0 else 30
        traffic_penalty = 0
        if avg_speed < 30:
            traffic_penalty = (30 - avg_speed) * 0.005
            adjusted_efficiency *= (1 - traffic_penalty)
            
        # 3. 경로 타입 보정 (고속 위주면 공기저항 추가)
        if route_priority == "HIGHWAY":
            adjusted_efficiency *= 0.95  # 5% 감소

        current_energy = capacity * (current_soc / 100.0)
        consumed_energy = road_distance / adjusted_efficiency
        remaining_energy = current_energy - consumed_energy
        remaining_soc = max((remaining_energy / capacity) * 100.0, 0.0)

        st.subheader("📊 주행 시뮬레이션 결과")

        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        with res_col1:
            st.metric("도착 예상 잔량", f"{remaining_soc:.1f}%", delta=f"{remaining_soc - current_soc:.1f}%")
        with res_col2:
            st.metric("주행 거리", f"{road_distance:.1f} km")
        with res_col3:
            st.metric("예상 소요 시간", f"{int(travel_time)} 분")
        with res_col4:
            st.metric("적용 전비", f"{adjusted_efficiency:.2f} km/kWh")

        if season != "봄/가을":
            st.warning(f"🌡️ 계절/온도 보정: {season}, 설정온도 {target_temp}°C")
        if traffic_penalty > 0:
            st.warning(f"🚗 교통 정체 보정: 평균 {int(avg_speed)}km/h로 운행")
        if route_priority == "HIGHWAY":
            st.warning("🛣️ 고속도로 주행: 공기 저항 보정 적용")

        if remaining_soc < 20:
            st.error("⚠️ 도착 잔량이 20% 미만입니다! 중간 충전소를 반드시 확인하세요.")
        else:
            st.success("✅ 쾌적하고 안전한 주행이 예상됩니다.")