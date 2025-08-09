import re
import requests
import types
import unicodedata
import pandas as pd

from pathlib import Path
from SPARQLWrapper import SPARQLWrapper, JSON, POST

GDB_URL = "http://localhost:7200"
REPO = "demo-semicon"

def create_classname_syntax(classname):
   return "".join([word.capitalize() for word in classname.replace("‑", " ").split()])

def clean_param_name(raw):
    # 1. Remove text in parentheses (units)
    raw = re.sub(r"\(.*?\)", "", raw)

    # 2. Normalize Unicode characters to ASCII equivalents
    raw = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode()

    # 3. Remove any remaining non-alphanumeric characters (except space and hyphen)
    raw = re.sub(r"[^\w\s-]", "", raw)

    # 4. Collapse multiple spaces and trim
    return re.sub(r"\s+", " ", raw).strip()

def extract_number(value):
    if pd.isna(value):
        return None
    value = str(value).replace("–", "-").replace("−", "-").replace(" ", "").replace(",", "")
    match = re.search(r"[-+]?\d*\.?\d+", value)
    return float(match.group()) if match else None

def perform_sparql_query(query):
    sparql = SPARQLWrapper(f"{GDB_URL}/repositories/{REPO}")
    sparql.setReturnFormat(JSON)
    sparql.setQuery(query)
    results = sparql.query().convert()
    return results

def perform_sparql_update(query):
    sparql = SPARQLWrapper(f"{GDB_URL}/repositories/{REPO}/statements")
    sparql.setMethod(POST)
    sparql.setRequestMethod(POST)
    sparql.setQuery(query)
    sparql.query()

def clear_graphdb_default_graph():
    url = f"{GDB_URL}/repositories/{REPO}/statements"
    r = requests.delete(url)
    if r.status_code == 204:
        print("Default graph cleared successfully.")
    else:
        print(f"Error clearing default graph: {r.status_code} {r.text}")

def export_ontology_to_graphdb(
        parent_ontology_path:str,
        individual_ontology_path:str
):
    # Upload to repository
    headers = {
        "Content-Type": "application/rdf+xml"
    }
    with open(parent_ontology_path, "rb") as f:
        r = requests.post(
            f"{GDB_URL}/repositories/{REPO}/statements",
            headers=headers,
            data=f
        )
    with open(individual_ontology_path, "rb") as f:
        r = requests.post(
            f"{GDB_URL}/repositories/{REPO}/statements",
            headers=headers,
            data=f
        )
    if r.status_code == 204:
        print("OWL file uploaded successfully.")
    else:
        print(f"Error uploading: {r.status_code} {r.text}")

def replace_iri():
   # File path to your ontology
    owl_file = Path("./data/ontologies/semicon-base.owl")

    # Original and replacement import IRIs
    original_iri = 'https://spec.industrialontologies.org/ontology/core/Core'
    replacement_iri = 'https://raw.githubusercontent.com/iofoundry/ontology/master/core/Core.rdf'

    # Load and replace in the file
    owl_text = owl_file.read_text()
    owl_text_modified = owl_text.replace(
        f'<owl:imports rdf:resource="{original_iri}"/>',
        f'<owl:imports rdf:resource="{replacement_iri}"/>'
    )

    # Overwrite the file (or write to a new file if you want to keep the original)
    owl_file.write_text(owl_text_modified)

    print("owl:imports IRI replaced successfully.")
  
def add_classes(classlist, parent_class, ontology):
   with ontology:
      for classname in classlist:
         onto_class = types.new_class(create_classname_syntax(classname), (parent_class,))
         onto_class.label.append(classname)

def add_individuals(individuals_list, ontology, parent_ontology):
    with ontology:
        for label, cls in individuals_list.items():
            ind = parent_ontology[create_classname_syntax(cls)](label)
            ind.label.append(label)