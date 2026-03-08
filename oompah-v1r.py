import requests

def run_task(url):
    try:
        response = requests.get(url)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"URL error: {e}")
        return None
