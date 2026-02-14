import argparse
import json
import os
import glob
import pandas as pd

from decimal import Decimal, ROUND_HALF_UP
from pymongo import MongoClient
from owlready2 import *

from app.models import *
from app.config.onto import data_rows, mode
from app.config.data_paths import folders, resources, ontologies

from app.services.utils import *
from app.services.causal_chain_gt import generate_causal_chain_gt
from .services.ontology_functions import initiate_ontology,\
    add_specs_to_ontology,\
    add_products_to_ontology,\
    add_dispositions_to_ontology
from app.services.ccc import perform_conformance_assessment_mlp
from app.services.causal_chains import (
    create_causal_chain, 
    infere_root_causes,
    attach_corrective_action_to_root_causes
)
from .services.metrics import collect_metrics

# db_client = MongoClient("mongodb://localhost:27017/")

#set the path where system generated ontologies will be saved
onto_path.append(folders.onto)

# good_ratio = 0.5
# bad_ratio = 0.5
# version = 3
# data_label = "train"
# defect_threshold = 0.55

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
    df = pd.read_csv(resources.specs, skiprows=1)
    target_cols = list(df.iloc[:, [0, 1, 2, 3, 4, 5, 6]].itertuples(index=False, name=None))
    #0:id 1:parameter 2:value 3:class 4:quality inheriter 5: process
    spec_category_dict = {}
    for row in target_cols:
        spec_name = row[1]
        spec_category = row[3].split(":")[1].strip()
        process_category = row[5].strip() if not pd.isna(row[5]) else None
        quality_inheritor = row[4].strip() if not pd.isna(row[4]) else None
        ppsc_ref =  row[6].strip() if not pd.isna(row[6]) else None
        spec_category_dict[normalize_text(spec_name.lower())] = {
            "onto_category": spec_category, 
            "process_category": process_category,
            "quality_inheritor": quality_inheritor,
            "ppsc_ref": ppsc_ref
        }
        spec_value = row[2]
        specs_dict[normalize_text(spec_name.lower())] = spec_value

    #chain the process
    #specs_dict = dict(list(specs_dict.items())[:3])
    parsed_spec_dict = parse_spec_strings(specs_dict)
    for k, v in parsed_spec_dict.items():
        parsed_spec_dict[k]['onto_category'] = spec_category_dict[k]['onto_category']
        parsed_spec_dict[k]['process_category'] = spec_category_dict[k]['process_category']
        parsed_spec_dict[k]["quality_inheritor"] = spec_category_dict[k]["quality_inheritor"]
        parsed_spec_dict[k]["ppsc_ref"] = spec_category_dict[k]["ppsc_ref"]
    #null specs
    null_specs = {
        name.lower(): values for name, values in parsed_spec_dict.items()
        if all(v is None for k, v in values.items() if k not in ["id", "category"])
    }
    #non-null specs
    non_null_specs = {s.lower(): v for s,v in parsed_spec_dict.items() if s.lower() not in null_specs}

    with open(resources.specs_json, "w") as f:
        json.dump(parsed_spec_dict, f, indent=2, ensure_ascii=False)

    return {"null_specs": null_specs, "non_null_specs": non_null_specs}

def extract_manufacturing_process_concepts(specs):
    mpc = []
    for k, v in specs.items():
        if v['process_category'] and v['process_category'] not in mpc:
            mpc.append(v['process_category'])
    return mpc

def extract_equipment_concepts():
    df = pd.read_csv(resources.equipments)
    target_cols = list(df.iloc[:, [0, 1, 2]].itertuples(index=False, name=None))
    equipment_data = []
    material_product_data = []
    for row in target_cols:
        if row[1] == "equipment":
            equipment_data.append(
                {
                    "equipment": row[0], 
                    "process_category": row[2]
                }
            )
        elif row[1] == "material product":
            material_product_data.append(
                {
                    "material_product": row[0], 
                    "process_category": row[2]
                }
            )
    return equipment_data, material_product_data

def extract_defect_causes_dispositions():
    fc_df = pd.read_csv(resources.failure_causes)
    fcs = {"defect": [], "failure_cause": [], "dispositions": []}
    target_cols = list(fc_df.iloc[:, [0, 1, 2, 3, 4]].itertuples(index=False, name=None))
    for row in target_cols:
        level = row[0].strip()
        item = row[1].strip()
        disposition = row[3].strip() if not pd.isna(row[3]) else None
        characteristic = row[4].strip() if not pd.isna(row[4]) else None
        if level == "defect":
            fcs['defect'].append(item)
        elif level == "mechanism" or level == "parameter":
            fcs['failure_cause'].append({"failure_cause": item, "characteristic": characteristic})
            if disposition:
                fcs['dispositions'].append(
                    {
                        "disposition": disposition,
                        "failure_cause": item,
                        "characteristic": characteristic
                    }
                )
    return fcs

def extract_axioms():
    axioms_df = pd.read_csv(resources.axioms)
    target_cols = list(axioms_df.iloc[:, [0, 1, 2, 3]].itertuples(index=False, name=None))
    axioms_dict = {}
    for row in target_cols:
        class_name = row[0]
        n_and_s_axioms = row[3]
        axioms_dict[class_name] = n_and_s_axioms
    return axioms_dict

def extract_definitions_and_examples():
    prop_df = pd.read_csv(resources.object_props_define)
    classes_df = pd.read_csv(resources.classes_define)
    target_class_cols = list(classes_df.iloc[:, [0, 2, 3]].itertuples(index=False, name=None))
    target_prop_cols = list(prop_df.iloc[:, [0, 4, 5]].itertuples(index=False, name=None))
    target_dict = {}
    for row in target_class_cols:
        target_dict[row[0]] = {"definition": row[1], "example": row[2]}
    for row in target_prop_cols:
        target_dict[row[0]] = {"definition": row[1], "example": row[2]}
    return target_dict

def build_extracted_data() -> ExtractedData:
    specs = extract_specs()
    mpc = extract_manufacturing_process_concepts(specs['non_null_specs'])
    equipments, materials = extract_equipment_concepts()
    fcs = extract_defect_causes_dispositions()
    axioms = extract_axioms()
    definitions = extract_definitions_and_examples()

    return ExtractedData(
        specs=specs['non_null_specs'],
        manufacturing_processes=mpc,
        equipments=equipments,
        material_products=materials,
        failure_data=fcs,
        axioms=axioms,
        definitions=definitions
    )

def build_products_df(ctx:PipelineContext):
    def is_empty(x):
        return pd.isna(x) or str(x).strip() == "" or str(x).strip() == "No Defect"

    def is_not_empty(x):
        return not is_empty(x)
    data_file = resources.test_data if ctx.runtime.mode == "test" else resources.ft_data
    df = pd.read_csv(data_file)
    df.columns = df.columns.str.strip()
    mask = (
        df["Defect"].apply(is_not_empty) |
        (
            df["Defect"].apply(is_empty) &
            (
                df["mech causes"].apply(is_not_empty) |
                df["root causes"].apply(is_not_empty)
            )
        )
    )
    df = df[mask].head(ctx.runtime.data_rows)
    return df

# Define step functions
def step_create_ground_truth(ctx:PipelineContext):
    ctx.runtime.chain_gt = generate_causal_chain_gt(ctx)

def step_init(ctx:PipelineContext):
    if ctx.runtime.create_ontology:
        initiate_ontology(
            ctx.runtime.create_ontology, 
            folders.onto, 
            resources.properties, 
            {
                "semicon_quality_concepts": {k : v for k,v in ctx.data.specs.items() if ctx.data.specs[k]['onto_category'] == 'Quality'},
                "semicon_characteristic_concepts": {k : v for k,v in ctx.data.specs.items() if ctx.data.specs[k]['onto_category'] == 'ProcessCharacteristic'},
                "manufacturing_process_concepts": ctx.data.manufacturing_processes,
                "defects_and_failure_causes": ctx.data.failure_data,
                "equipments_data": ctx.data.equipments,
                "material_products_data": ctx.data.material_products
            }, 
            ctx.data.axioms, 
            ctx.data.definitions
        )
    else:
        initiate_ontology(
            ctx.runtime.create_ontology
        )

def step_specs(ctx:PipelineContext):
    add_specs_to_ontology(ctx.data.specs, folders.onto)

def step_dispositions(ctx:PipelineContext):
    add_dispositions_to_ontology(ctx.data.failure_data, folders.onto)

def step_products(ctx:PipelineContext):
    return add_products_to_ontology(
        ctx.runtime.factory_data,
        folders.onto
    )

def step_clear_db(ctx:PipelineContext):
    clear_graphdb_default_graph()

def step_export(ctx:PipelineContext):
    export_ontology_to_graphdb([
        ontologies.bfo,
        ontologies.bfo_prov,
        ontologies.iof,
        ontologies.ro,
        ontologies.terms,
        ontologies.assertions
    ])

def step_generate_causal_hypothesis(ctx:PipelineContext):
    perform_conformance_assessment_mlp(ctx)
    create_causal_chain(verb="INSERT")
    infere_root_causes(verb="INSERT")
    # attach_corrective_action_to_root_causes(verb="INSERT")
    print("✅ GraphDB update completed successfully")

def step_generate_metrics(ctx:PipelineContext):
    collect_metrics(ctx)

PIPELINE = [
    ("ground_truth", step_create_ground_truth),
    ("init", step_init),
    ("specs", step_specs),
    ("dispositions", step_dispositions),
    ("products", step_products),
    ("clear_db", step_clear_db),
    ("export", step_export),
    ("causal_hypothesis", step_generate_causal_hypothesis),
    ("metrics", step_generate_metrics)
]

def run_pipeline(steps=None, ctx=None):
    ctx = ctx or {}

    for name, fn in PIPELINE:
        if steps and name not in steps:
            continue

        print(f"Running step: {name}")
        result = fn(ctx)
    return ctx

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SemicON Ontology CLI")
    parser.add_argument("--steps", nargs="+", help="Steps to run")
    args = parser.parse_args()
    create_ontology = True
    onto_data = build_extracted_data()
    runtime = PipelineRunTime(
        mode=mode, 
        create_ontology=create_ontology,
        data_rows=data_rows
    )
    ctx = PipelineContext(data=onto_data, runtime=runtime)
    ctx.runtime.factory_data = build_products_df(ctx)
    run_pipeline(args.steps, ctx)