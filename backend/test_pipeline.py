import httpx, json

tests = [
    ('bad_signature_test.rim95', b'236'),
    ('bad.rim95', b'\xff\xfe9\x00\r\x00\n\x00'),
]

for name, content in tests:
    r = httpx.post('http://localhost:8000/api/upload', files={'file': (name, content, 'application/octet-stream')})
    d = r.json()
    with open(f'test_result_{name}.json', 'w') as f:
        json.dump(d, f, indent=2)
    print(f"Saved test_result_{name}.json")
