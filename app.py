import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import xmltodict
from streamlit_cookies_controller import CookieController

# 페이지 설정
st.set_page_config(page_title="스마트 EV 전비 계산기", page_icon="⚡", layout="wide")

# 쿠키 컨트롤러 초기화
controller = CookieController()

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

# 1. 전기차 모델 데이터 설정 (공공데이터 API 연동 - 인증정보 활용)
@st.cache_data(ttl=86400) # 24시간마다 캐시 갱신
def get_ev_models_with_specs(gubun="1", certiDate="2023"):
    try:
        api_key = st.secrets["PUBLIC_DATA_API_KEY"]
        base_url = "https://apis.data.go.kr/1480523/KencisEV/getEVCert"
        url = f"{base_url}?serviceKey={api_key}&pageNo=1&numOfRows=100&resultType=XML&gubun={gubun}&certiDate={certiDate}"

        response = requests.get(url)
        if response.status_code == 200:
            data_dict = xmltodict.parse(response.text)
            items = data_dict.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items, dict): items = [items]

            # {제조사: {모델명: {상온전비: ..., 저온전비: ...}}} 구조
            ev_data = {}
            for item in items:
                brand = item.get("officenm", "기타").split(' ')[0]
                model_name = item["vehnm"]
                # 상온 복합(dstchrrdistrtempcpx) / 저온 복합(dstchrrdistlowtmpcpx)
                norm_range = float(item["dstchrrdistrtempcpx"]) if item["dstchrrdistrtempcpx"] != "-" else 300.0
                low_range = float(item["dstchrrdistlowtmpcpx"]) if item["dstchrrdistlowtmpcpx"] != "-" else 200.0

                if brand not in ev_data: ev_data[brand] = {}
                ev_data[brand][model_name] = {"norm_range": norm_range, "low_range": low_range}
            return ev_data
    except Exception as e:
        st.error(f"API 호출 오류: {e}")
    return {"기본": {"BMW i4": {"norm_range": 350.0, "low_range": 250.0}}}

# ... (UI 레이아웃 일부 유지)

    # 모델 선택
    models_dict = ev_data[selected_brand]
    selected_model = st.selectbox("모델 선택", list(models_dict.keys()))

    # 선택된 모델의 상세 정보
    specs = models_dict[selected_model]

    # 현재 계절에 따른 기본 주행거리 설정
    import datetime
    current_month = datetime.date.today().month
    season = "여름" if 6 <= current_month <= 8 else "겨울" if current_month <= 2 or current_month >= 12 else "봄/가을"

    # 겨울이면 저온 주행거리 사용, 그 외는 상온 주행거리 사용
    base_range = specs["low_range"] if season == "겨울" else specs["norm_range"]

    current_soc = st.slider("현재 배터리 잔량 (%)", 0, 100, 80)

    # 상온 주행거리 기준 전비 입력 (사용자 수정 가능)
    base_efficiency = st.number_input("기준 주행가능거리 (km)", min_value=100.0, value=float(base_range), step=1.0)



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
    
    # 저장된 설정 불러오기 (getAll 사용)
    saved_config = controller.getAll()
    
    # API 호출 파라미터 설정
    gubun_map = {"수입차": "1", "국내차": "2"}
    
    # 쿠키에서 설정값 로드
    def_gubun = saved_config.get("gubun", "수입차")
    def_year = saved_config.get("year", "2023")
    
    selected_gubun_name = st.radio("차량 분류", list(gubun_map.keys()), index=list(gubun_map.keys()).index(def_gubun))
    selected_gubun = gubun_map[selected_gubun_name]
    selected_year = st.text_input("제조년도", value=def_year)
    
    # 데이터 가져오기
    ev_data = get_ev_models_with_specs(gubun=selected_gubun, certiDate=selected_year)
    
    # 세션 상태 초기화 및 쿠키 연동
    if "selected_brand" not in st.session_state:
        st.session_state.selected_brand = saved_config.get("brand", sorted(list(ev_data.keys()))[0])
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = saved_config.get("model", list(ev_data[st.session_state.selected_brand].keys())[0])
    if "base_efficiency" not in st.session_state:
        st.session_state.base_efficiency = float(saved_config.get("efficiency", 5.0))
        
    def update_model():
        st.session_state.selected_model = st.session_state.model_selector
        specs = ev_data[st.session_state.selected_brand][st.session_state.selected_model]
        st.session_state.base_efficiency = specs.get("norm_range", 300.0) / 60.0
        # 설정 저장
        controller.set("gubun", selected_gubun_name)
        controller.set("year", selected_year)
        controller.set("brand", st.session_state.selected_brand)
        controller.set("model", st.session_state.selected_model)
        controller.set("efficiency", st.session_state.base_efficiency)

    def update_brand():
        st.session_state.selected_brand = st.session_state.brand_selector
        # 브랜드 변경 시 모델을 해당 브랜드의 첫 번째 모델로 초기화
        st.session_state.selected_model = list(ev_data[st.session_state.selected_brand].keys())[0]
        specs = ev_data[st.session_state.selected_brand][st.session_state.selected_model]
        st.session_state.base_efficiency = specs.get("norm_range", 300.0) / 60.0
        # 설정 저장
        controller.set("brand", st.session_state.selected_brand)
        controller.set("model", st.session_state.selected_model)
        controller.set("efficiency", st.session_state.base_efficiency)

    # 2단계 모델 선택 UI
    brands = sorted(list(ev_data.keys()))
    # 브랜드가 유효한지 확인
    brand_index = brands.index(st.session_state.selected_brand) if st.session_state.selected_brand in brands else 0
    st.selectbox("제조사 선택", brands, key="brand_selector", index=brand_index, on_change=update_brand)
    
    models_dict = ev_data[st.session_state.selected_brand]
    
    # 모델 셀렉터 인덱스 관리
    model_list = list(models_dict.keys())
    model_index = model_list.index(st.session_state.selected_model) if st.session_state.selected_model in model_list else 0
    st.selectbox("모델 선택", model_list, key="model_selector", index=model_index, on_change=update_model)
    
    # 배터리 용량은 데이터가 없으므로 임시 기본값 사용
    capacity = 75.0 
    
    current_soc = st.slider("현재 배터리 잔량 (%)", 0, 100, 80)
    base_efficiency = st.number_input("기준 전비 (km/kWh)", min_value=0.1, value=st.session_state.base_efficiency, step=0.1)

    st.divider()
    st.markdown("📍 **주행 상세 설정**")

    # 1. 경로 타입 선택
    route_priority = st.selectbox("경로 우선순위", ["RECOMMEND", "HIGHWAY", "ROAD"], 
                                 format_func=lambda x: {"RECOMMEND": "추천 경로", "HIGHWAY": "고속도로 우선", "ROAD": "국도 우선"}[x])

    # ... (생략된 기존 UI 요소들) ...

# --- 유튜브 채널 최신 영상 가져오기 함수 ---
@st.cache_data(ttl=3600) # 1시간마다 갱신
def get_latest_youtube_video(channel_id):
    try:
        api_key = st.secrets["YOUTUBE_API_KEY"]
        import re
        
        def parse_duration(duration):
            # ISO 8601 형식: PT1H2M30S 또는 PT55S
            hours = re.search(r'(\d+)H', duration)
            minutes = re.search(r'(\d+)M', duration)
            seconds = re.search(r'(\d+)S', duration)
            h = int(hours.group(1)) if hours else 0
            m = int(minutes.group(1)) if minutes else 0
            s = int(seconds.group(1)) if seconds else 0
            return h * 3600 + m * 60 + s

        # 1. 채널의 업로드 영상 목록(재생목록 ID) 가져오기
        url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}&key={api_key}"
        res = requests.get(url).json()
        playlist_id = res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # 2. 최근 영상 10개 가져오기
        url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=10&playlistId={playlist_id}&key={api_key}"
        res = requests.get(url).json()
        video_ids = [item['snippet']['resourceId']['videoId'] for item in res['items']]
        
        # 3. 각 영상의 길이 확인 (Shorts 필터링)
        url = f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id={','.join(video_ids)}&key={api_key}"
        res = requests.get(url).json()
        
        for item in res['items']:
            if parse_duration(item['contentDetails']['duration']) > 60:
                return item['id']
                
    except Exception as e:
        return None
    return None

# --- UI 레이아웃 시작 ---
with st.sidebar:
    # ... (생략) ...
    
    # AI 음악 채널 배너 (사이드바 하단)
    st.divider()
    st.subheader("🎵 AI 음악 채널 (최신곡)")
    channel_id = st.secrets.get("YOUTUBE_CHANNEL_ID", "YOUR_CHANNEL_ID")
    video_id = get_latest_youtube_video(channel_id)
    if video_id:
        st.video(f"https://www.youtube.com/watch?v={video_id}", autoplay=True, muted=True)
    else:
        st.error("최신 일반 영상을 가져오는데 실패했습니다.")

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
        <span class="gps-label">🎯 아래 GPS 목표 아이콘을 클릭해 현재 위치를 파악하세요:</span>
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
        # base_efficiency는 이제 상온 주행가능거리(km)입니다.
        adjusted_range = base_efficiency
        
        # 1. 온도/계절 보정 (간단 모델)
        temp_diff = abs(target_temp - end_temp)
        if season == "겨울":
            # 겨울엔 기온 낮으면 큰 페널티
            penalty = (max(0, 20 - end_temp)) * 0.02 + (temp_diff * 0.005)
            adjusted_range *= (1 - penalty)
        elif season == "여름":
            # 여름엔 기온 높으면 페널티
            penalty = (max(0, end_temp - 25)) * 0.01 + (temp_diff * 0.003)
            adjusted_range *= (1 - penalty)
        
        # 2. 교통 보정
        avg_speed = road_distance / (travel_time / 60) if travel_time > 0 else 30
        traffic_penalty = 0
        if avg_speed < 30:
            traffic_penalty = (30 - avg_speed) * 0.005
            adjusted_range *= (1 - traffic_penalty)
            
        # 3. 경로 타입 보정 (고속 위주면 공기저항 추가)
        if route_priority == "HIGHWAY":
            adjusted_range *= 0.95  # 5% 감소

        # 거리 기반 잔량 계산
        # 남은 잔량(%) = 현재_잔량(%) - (주행거리 / 보정된_주행가능거리 * 100)
        consumed_soc = (road_distance / adjusted_range) * 100.0
        remaining_soc = max(current_soc - consumed_soc, 0.0)

        st.subheader("📊 주행 시뮬레이션 결과")

        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        with res_col1:
            st.metric("도착 예상 잔량", f"{remaining_soc:.1f}%", delta=f"{remaining_soc - current_soc:.1f}%")
        with res_col2:
            st.metric("주행 거리", f"{road_distance:.1f} km")
        with res_col3:
            st.metric("예상 소요 시간", f"{int(travel_time)} 분")
        with res_col4:
            st.metric("보정 주행가능거리", f"{adjusted_range:.1f} km")

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