import requests

url = "http://127.0.0.1:8000/api/"
data = {
    "phone": "+998901234567" 
}

response = requests.post(url, json=data)

print("Status code:", response.status_code)
print("Natija:")
print(response.json())
