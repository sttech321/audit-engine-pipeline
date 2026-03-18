import httpx

r = httpx.post(
    "http://localhost:8000/api/upload",
    files={"file": open("d:/wamp64/www/RIMOS/bad_signature.rim95", "rb")}
)
data = r.json()
v = data["verification"]
k = data["kpis"]
print("Status:", v["status"])
print("Confidence:", v["confidence"])
print("Checks:", v["checks"])
score = next(x["value"] for x in k if x["label"] == "Audit Score")
print("Score:", score)
