import requests
import streamlit as st
import xmltodict  # XML 파싱을 위해 추가

try:
    api_key = st.secrets["PUBLIC_DATA_API_KEY"]
    # 사용자가 찾은 EV 인증 정보 API
    url = "https://apis.data.go.kr/1480523/KencisEV/getEVCert"
    params = {
        "serviceKey": api_key,
        "pageNo": "1",
        "numOfRows": "100",
        "resultType": "XML",
        "gubun": "1",
        "certiDate": "2022"
    }
    response = requests.get(url, params=params)
    print(response.text)
    print(api_key)
    if response.status_code == 200:
        print("성공")

except Exception as e:
    st.error(f"API 호출 오류: {e}")



