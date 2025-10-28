import argparse
import json
import os
import pandas as pd

from decimal import Decimal, ROUND_HALF_UP
from owlready2 import *

from app.services.utils import *
from .services.ontology_functions import initiate_ontology,\
    add_specs_to_ontology,\
    add_products_to_ontology
from .services.bayesian_inference import implement_bayesian_inference


base_path = "./app/data"
path = f"{base_path}/ontologies/epoch3-7"
input_path = f"{base_path}/input/epoch3-7"
output_path = f"{base_path}/output/epoch3-7"
specs_file = f"{input_path}/specs_data.csv"
fc_file = f"{input_path}/defects_and_failure_causes.csv"

#set the path where system generated ontologies will be saved
onto_path.append(path)

good_ratio = 0.5
bad_ratio = 0.5
version = 3
products_in_ontology = 9999
data_label = "train"
defect_threshold = 0.55

def parse_rule(rule: str):
    rule = normalize_text(rule)
    result = {}
    # Regex to capture spec name, comparator, value, unit
    pattern = re.compile(
        r"\(?\s*([A-Za-z0-9\s\-]+?)\s*(>=|<=|=|==|>|<)\s*([-+]?\d*\.?\d+)\s*[^\s\)]*\)?"
    )
    for match in pattern.finditer(rule):
        spec, comp, value = match.groups()
        spec = spec.strip()
        # Map comparator symbols to words
        comp_map = {
            ">": "more_than",
            "<": "less_than",
            ">=": "more_than_equal",
            "<=": "less_than_equal",
            "=": "equal",
            "==": "equal",
        }
        comparator = comp_map[comp]
        value = float(value)
        if spec.lower() not in result:
            result[spec.lower()] = []
        result[spec.lower()].append({"comparator": comparator, "value": value})
    return result

def make_result(nominal=None, tol=None, upper=None, lower=None, units=None):
    return {
        "NOM": nominal,
        "tolerance": tol,
        "USL": upper,
        "LSL": lower,
        "units": units
    }

def regex_parse_spec_string(spec: str):
    spec = spec.strip()
    # Pattern 1: Nominal ± tolerance (e.g., "10±0.5mm")
    m = re.match(r"(\d+\.?\d*)\s*([^\d±]*)\s*±\s*(\d+\.?\d*)\s*([^\d±]*)", spec)
    if m:
        nominal, unit1, tol, unit2 = m.groups()
        unit = unit1 or unit2 or None
        unit = re.sub(r"\s+", " ", unit).strip() if unit else None
        nominal = Decimal(nominal).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        tol = Decimal(tol).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP) if float(tol) > 0 else 0
        upper = (nominal + tol).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        lower = (nominal - tol).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        return make_result(float(nominal), float(tol), float(upper), float(lower), unit)
    # Pattern 2: Just nominal + unit (e.g., "20kg")
    m = re.match(r"(\d+\.?\d*)\s*([a-zA-Z%]+)", spec)
    if m:
        nominal, units = m.groups()
        nominal = Decimal(nominal).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        tol = 0
        upper = (nominal + tol).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        lower = (nominal - tol).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        return make_result(float(nominal), 0, float(upper), float(lower), units or None)
    #Pattern 3: upper value and lower value given
    m = re.match(
        r"(\d+\.?\d*)\s*([^\d±–-]*)?\s*[–-]\s*(\d+\.?\d*)\s*([^\d±–-]*)?",
        spec
    )
    if m:
        low, unit1, high, unit2 = m.groups()
        low, high = float(low), float(high)
        nominal = round((low + high) / 2, 4)
        tol = round((high - low) / 2, 4)
        unit = (unit1.strip() if unit1 else "") or (unit2.strip() if unit2 else "") or None
        return make_result(nominal, tol, high, low, unit)
    #Pattern4: one of lower bound or upper bound fiven
    pattern = re.compile(r"(<=|>=|<|>|=|==|≤|≥)\s*([\d\.]+)\s*([^\d]*)?")
    m = pattern.search(spec)
    if m:
        comp, value, unit = m.groups()
        value = float(Decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
        if comp in ("≤", "<=", "<"):
            return make_result(None, None, value, None, unit)
        elif comp in ("≥", ">=", ">"):
            return make_result(None, None, None, value, unit)
        elif comp in ("=", "=="):
            return make_result(value, 0, value, value, unit)
    return None

def parse_spec_strings(specs_dict):
    extracted_specs_dict = {}
    spec_id = 0
    for k, v in specs_dict.items():
        # First try regex (fast + local)
        specs_output = regex_parse_spec_string(v)
        if specs_output:
            extracted_specs_dict[k] = specs_output
        else:
            extracted_specs_dict[k] = make_result()
        extracted_specs_dict[k]['id'] = f"S{spec_id + 1}"
        spec_id += 1
    return extracted_specs_dict

def extract_specs():
    specs_dict = {}
    df = pd.read_csv(specs_file, skiprows=2)
    target_cols = list(df.iloc[:, [0, 1, 2, 3, 4, 5]].itertuples(index=False, name=None))
    spec_category_dict = {}
    for row in target_cols:
        spec_name = row[1]
        spec_category = row[2].split(":")[1].strip()
        process_category = row[3].strip()
        spec_category_dict[normalize_text(spec_name.lower())] = {"onto_category": spec_category, "process_category": process_category}
        spec_value = row[4]
        specs_dict[normalize_text(spec_name.lower())] = spec_value
    #chain the process
    # specs_dict = dict(list(specs_dict.items())[:3])
    parsed_spec_dict = parse_spec_strings(specs_dict)
    for k, v in parsed_spec_dict.items():
        parsed_spec_dict[k]['onto_category'] = spec_category_dict[k]['onto_category']
        parsed_spec_dict[k]['process_category'] = spec_category_dict[k]['process_category']

    with open(f"{output_path}/specs.json", "w") as f:
        json.dump(parsed_spec_dict, f, indent=2, ensure_ascii=False)
    return parsed_spec_dict

specs = extract_specs()
#where all values are null
null_specs = {
    name.lower(): values for name, values in specs.items()
    if all(v is None for k, v in values.items() if k not in ["id", "category"])
}
#non-null specs
non_null_specs = {s.lower(): v for s,v in specs.items() if s.lower() not in null_specs}

manufacturing_process_concepts = []
for k, v in non_null_specs.items():
    if v['process_category'] not in manufacturing_process_concepts:
        manufacturing_process_concepts.append(v['process_category'])

fc_df = pd.read_csv(fc_file)
fc_df_dict = dict(zip(fc_df['item'], fc_df['level']))
fcs = {"defect": [], "failure_cause": []}
for k, v in fc_df_dict.items():
    if v == "defect":
        fcs['defect'].append(k)
    else:
        fcs['failure_cause'].append(k)

def extract_axioms():
    axioms_df = pd.read_csv(f"{input_path}/axioms.csv")
    target_cols = list(axioms_df.iloc[:, [0, 1, 2, 3, 4]].itertuples(index=False, name=None))
    axioms_dict = {}
    for row in target_cols:
        class_name = row[0]
        n_and_s_axioms = row[4]
        axioms_dict[class_name] = n_and_s_axioms
    return axioms_dict

def extract_definitions_and_examples():
    prop_df = pd.read_csv(f"{input_path}/definitions_and_examples_object_properties.csv")
    classes_df = pd.read_csv(f"{input_path}/definitions_and_examples_classes.csv")
    target_class_cols = list(classes_df.iloc[:, [0, 4, 5]].itertuples(index=False, name=None))
    target_prop_cols = list(prop_df.iloc[:, [0, 8, 9]].itertuples(index=False, name=None))
    target_dict = {}
    for row in target_class_cols:
        target_dict[row[0]] = {"definition": row[1], "example": row[2]}
    for row in target_prop_cols:
        target_dict[row[0]] = {"definition": row[1], "example": row[2]}
    return target_dict

axioms_dict = extract_axioms()
definitions_dict = extract_definitions_and_examples()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SemicON Ontology CLI")

    parser.add_argument("--init", action="store_true", help="Initiate ontology (create_new=False)")
    parser.add_argument("--init-new", action="store_true", help="Initiate ontology (create_new=True)")
    parser.add_argument("--add-specs", action="store_true", help="Add specifications")
    parser.add_argument("--add-products", action="store_true", help="Add products")
    parser.add_argument("--run-rules", action="store_true", help="Add and run SWRL rules")
    parser.add_argument("--export", action="store_true", help="Export ontology to GraphDB")
    parser.add_argument("--report", action="store_true", help="Generate failure reports")
    parser.add_argument("--clear", action="store_true", help="Clear the default graph in GraphDB")
    parser.add_argument("--evaluation-matrix", action="store_true", help="Generate evaluation matrix")
    parser.add_argument("--implement-bayes-inf", action="store_true", help="Implement bayesian inference")
    parser.add_argument("--remove-output-files", action="store_true", help="remove output files given version and path")

    args = parser.parse_args()

    if args.init:
        initiate_ontology(
            False
        )

    elif args.init_new:
        initiate_ontology(
            True,
            path,
            f"{input_path}/ontology_properties.yml",
            {
                "semicon_quality_concepts": {k : v for k,v in non_null_specs.items() if non_null_specs[k]['onto_category'] == 'Quality'},
                "semicon_characteristic_concepts": {k : v for k,v in non_null_specs.items() if non_null_specs[k]['process_category'] == 'ProcessCharacteristic'},
                "manufacturing_process_concepts": manufacturing_process_concepts,
                "defects_and_failure_causes": fcs
            },
            axioms_dict,
            definitions_dict
        )

    if args.add_specs:
        add_specs_to_ontology(
            non_null_specs,
            path
        )

    if args.add_products:
        add_products_to_ontology(
            products_in_ontology,
            f"{input_path}/synthetic_data_factory.csv",
            fcs,
            non_null_specs,
            path
        )

    if args.export:
        export_ontology_to_graphdb(
            parent_ontology_path = f"{path}/semicon-base.owl",
            individual_ontology_path = f"{path}/semicon-product1.owl"
        )
    if args.clear:
        clear_graphdb_default_graph()

    if args.implement_bayes_inf:
        train_dcm = f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_train.csv"
        test_dcm = f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_test.csv"
        implement_bayesian_inference(
            train_dcm,
            test_dcm,
            output_path,
            f"{good_ratio}_{bad_ratio}_v{version}",
            defect_threshold
        )

    if args.remove_output_files:
        remove_version_files(
            base_path,
            "output/epoch3-6",
            version_number=3
        )

