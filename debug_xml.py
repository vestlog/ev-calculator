import requests
import xmltodict

def get_key():
    with open(".streamlit/secrets.toml", "r") as f:
        for line in f:
            if line.startswith("PUBLIC_DATA_API_KEY"):
                return line.split("=")[1].strip().replace('"', "")
    return None

api_key = get_key()

base_url = "https://apis.data.go.kr/1480523/KencisEV/getEVCert"
url = f"{base_url}?serviceKey={api_key}&pageNo=1&numOfRows=100&resultType=XML&gubun=1&certiDate=2023"

response = requests.get(url)
print(f"Status Code: {response.status_code}")

if response.status_code == 200:
    data_dict = xmltodict.parse(response.text)
    items = data_dict.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
    
    # 모든 모델명 출력
    for item in items:
        print(f"Found: {item.get('vehnm', 'N/A')}")
else:
    print(response.text)
