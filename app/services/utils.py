import os
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
    if len(parts) > 1:
        return "".join(word.capitalize() for word in parts if word)
    elif len(parts) == 1:
        return parts[0]

def clean_param_name(raw):
    # 1. Remove text in parentheses (units)
    raw = re.sub(r"\(.*?\)", "", raw)

    # 2. Normalize Unicode characters to ASCII equivalents
    raw = unicodedata.normalize('NFKD', raw).encode('ascii', 'ignore').decode()

    # 3. Remove any remaining non-alphanumeric characters (except space and hyphen)
    raw = re.sub(r"[^\w\s-]", "", raw)

    # 4. Collapse multiple spaces and trim
    return re.sub(r"\s+", " ", raw).strip()

def normalize_text(text: str) -> str:
    # Replace all unicode whitespace (incl. \u202f, \u00a0, etc.) with plain space
    return re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()

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
    ontology_paths:list
):
    # Upload to repository
    headers = {
        "Content-Type": "application/rdf+xml"
    }
    for op in ontology_paths:
        with open(op, "rb") as f:
            r = requests.post(
                f"{GDB_URL}/repositories/{REPO}/statements",
                headers=headers,
                data=f
            )
            if r.status_code == 204:
                print(f"{op} OWL file uploaded successfully.")
            else:
                print(f"Error uploading: {r.status_code} {r.text}")

def replace_iri(path):
   # File path to your ontology
    owl_file = Path(path)

    # Original and replacement import IRIs
    original_iri_iof = 'https://spec.industrialontologies.org/ontology/core/Core'
    replacement_iri_iof = 'https://raw.githubusercontent.com/iofoundry/ontology/master/core/Core.rdf'

    # Load and replace in the file
    owl_text = owl_file.read_text()
    owl_text_modified = owl_text.replace(
        f'<owl:imports rdf:resource="{original_iri_iof}"/>',
        f'<owl:imports rdf:resource="{replacement_iri_iof}"/>'
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

def remove_version_files(base_path: str, folder: str, version_number: int):
    """
    Removes all files containing the given version number (like v1, v2, etc.)
    inside the specified folder ('input' or 'output'), including subdirectories.

    Args:
        base_path (str): Root directory path (e.g. '/home/user/project/app/data')
        folder (str): Subfolder name ('input' or 'output')
        version_number (int): Version number to match (e.g. 1, 2, 3)
    """
    target_dir = os.path.join(base_path, folder)
    pattern = re.compile(fr"(?<![a-zA-Z0-9])v{version_number}(?![a-zA-Z0-9])", re.IGNORECASE)
    removed_files = []

    if not os.path.exists(target_dir):
        print(f"❌ Folder not found: {target_dir}")
        return

    for root, _, files in os.walk(target_dir):
        for file in files:
            if pattern.search(file):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    removed_files.append(file_path)
                except Exception as e:
                    print(f"⚠️ Could not remove {file_path}: {e}")

    if removed_files:
        print(f"✅ Removed {len(removed_files)} files containing v{version_number}:")
        for f in removed_files:
            print(f"  - {f}")
    else:
        print(f"ℹ️ No files found containing v{version_number} in '{folder}'.")

def extract_rule_directions(expr: str):
    conditions = re.findall(r"\((.*?)\)", expr)
    param_dict = {}
    for cond in conditions:
        match = re.match(r"(.+?)\s*(<=|>=|<|>)\s*(.+)", cond.strip())
        if match:
            param, op, _ = match.groups()
            param = normalize_text(param.strip().lower())
            if param not in param_dict:
                param_dict[param] = []
            if op in (">", ">="):
                param_dict[param].append("UL")
            if op in ("<", "<="):
                param_dict[param].append("LL")
    return param_dict
