import requests
from SPARQLWrapper import SPARQLWrapper, JSON

GDB_URL = "http://localhost:7200"
REPO = "demo-semicon"
sparql = SPARQLWrapper(f"{GDB_URL}/repositories/{REPO}")

def perform_sparql_query(query):
    sparql.setReturnFormat(JSON)
    sparql.setQuery(query)
    results = sparql.query().convert()
    return results

def clear_graphdb_default_graph():
    url = f"{GDB_URL}/repositories/{REPO}/statements"
    r = requests.delete(url)
    if r.status_code == 204:
        print("Default graph cleared successfully.")
    else:
        print(f"Error clearing default graph: {r.status_code} {r.text}")

def export_ontology_to_graphdb(path):
    base_onto_path = f"{path}/semicon-base.owl"
    product1_path = f"{path}/semicon-product1.owl"
    # Upload to repository
    headers = {
        "Content-Type": "application/rdf+xml"
    }
    with open(base_onto_path, "rb") as f:
        r = requests.post(
            f"{GDB_URL}/repositories/{REPO}/statements",
            headers=headers,
            data=f
        )
    with open(product1_path, "rb") as f:
        r = requests.post(
            f"{GDB_URL}/repositories/{REPO}/statements",
            headers=headers,
            data=f
        )
    if r.status_code == 204:
        print("OWL file uploaded successfully.")
    else:
        print(f"Error uploading: {r.status_code} {r.text}")