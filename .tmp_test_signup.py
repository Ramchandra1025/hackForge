from app import app

client = app.test_client()
response = client.post('/api/auth/signup/initiate', json={
    'email': 'testuser12345@example.com',
    'username': 'testuser12345',
    'password': 'StrongPass123!'
})
print(response.status_code)
print(response.get_data(as_text=True))
