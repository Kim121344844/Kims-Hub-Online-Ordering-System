import requests

# Test the /api/approved_reviews endpoint (should return empty list initially)
response = requests.get('http://127.0.0.1:5000/api/approved_reviews')
print("/api/approved_reviews:")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Test the /api/reviews endpoint without authentication (should return 401)
response = requests.get('http://127.0.0.1:5000/api/reviews')
print("/api/reviews (unauthenticated):")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Test submit_review without authentication (should return 401)
response = requests.post('http://127.0.0.1:5000/submit_review', json={
    'order_id': 'test123',
    'rating': 5,
    'comment': 'Great food!'
})
print("/submit_review (unauthenticated):")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Test approve_review without authentication (should return 401)
response = requests.post('http://127.0.0.1:5000/approve_review/1')
print("/approve_review (unauthenticated):")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
print()

# Test delete_review without authentication (should return 401)
response = requests.post('http://127.0.0.1:5000/delete_review/1')
print("/delete_review (unauthenticated):")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")
print()
