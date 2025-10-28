import requests

# GraphDB repository URL
repo = "demo-semicon-shacl"
graphdb_url = f"http://localhost:7200/rest/repositories/{repo}/validate/file"

# Path to your SHACL shapes file
shapes_file = "./app/data/input/epoch3-7/shapes.ttl"

# Make the POST request
with open(shapes_file, "rb") as f:
    response = requests.post(
        graphdb_url,
        headers={"Accept": "text/turtle"},   # Ask for Turtle response
        files={"file": ("shapes.ttl", f, "text/turtle")}
    )

# Handle the response
if response.status_code == 200:
    print("✅ Validation completed successfully.")
    print(response.text)   # This is your SHACL validation report (in Turtle)
else:
    print(f"❌ Validation failed: {response.status_code}")
    print(response.text)