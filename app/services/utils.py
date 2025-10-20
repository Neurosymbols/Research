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
   # Split by any sequence of non-alphanumeric characters
    parts = re.split(r'[^A-Za-z0-9]+', classname)
    # Capitalize each part and join
    return "".join(word.capitalize() for word in parts if word)

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

def create_interaction_rules_for_sparql(rule_scores: dict):
    interaction_rules_sparql = []
    
    # Iterate through the dictionary items (k=tuple of rules, v=score)
    for k, v in rule_scores.items():
        exists_statements = []
        
        # Build the EXISTS block content
        for rule in k:
            # Note: Removed the trailing space from the f-string for robustness
            exists_statements.append(
                f"?defect base:hasFailureCause product1:{rule} ."
            )
        
        # Join the EXISTS statements with newlines
        exists_block = "\n".join(exists_statements)
        
        # Construct the final SPARQL rule using a clean triple-quoted string
        # Ensure the embedded f-string expression (v) is not near confusing indentation
        interaction = f"""
            IF(
                EXISTS{{
                    {exists_block}
                }},
                {v},
                0
            )
        """
        # Strip excess leading/trailing whitespace before appending
        interaction_rules_sparql.append(interaction.strip())
        
    # Join all interaction rules with the '+' operator for SPARQL expression
    interaction_rules_sparql = "\n+\n".join(interaction_rules_sparql)
    return interaction_rules_sparql

def get_failure_cause_concepts(failure_causes_rules_mapping):
    failure_cause_concepts = {}
    for defect, defect_info in failure_causes_rules_mapping.items():
        for fc_name, fc_data in defect_info.items():
            if fc_name not in failure_cause_concepts:
                failure_cause_concepts[fc_name] = fc_data
    return failure_cause_concepts

def get_rule_scores(interaction_rules_file):
    interaction_bonuses_df = pd.read_csv(interaction_rules_file)
    target_cols = list(interaction_bonuses_df.iloc[:, [1, 4]].itertuples(index=False, name=None))
    rule_scores = {}
    for row in target_cols:
        rule_comb = tuple([f"FC{r.strip()}" for r in row[0].split("+")])
        rule_scores[rule_comb] = row[1]
    return rule_scores
