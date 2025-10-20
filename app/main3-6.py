import argparse
import json
import os
import pandas as pd

from decimal import Decimal, ROUND_HALF_UP
from owlready2 import *

from app.services.utils import *
from .services.ontology_functions import initiate_ontology,\
    add_specs_to_ontology,\
    add_products_to_ontology,\
    run_rules
from .services.create_reports import generate_blind_defect_cause_matrix
from .services.bayesian_inference import implement_bayesian_inference
from .tests import *


GEMINI_API_KEY = "AIzaSyAlP3WbsB0VqdVEnZ-_Dw22C5XcW51Uvcg"
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

base_path = "./app/data"
path = f"{base_path}/ontologies/epoch3-6"
input_path = f"{base_path}/input/epoch3-6"
output_path = f"{base_path}/output/epoch3-6"
specs_file = f"{input_path}/specs_data_sp.csv"
fmea_file = f"{input_path}/fmea-bidirectional.csv"

#set the path where system generated ontologies will be saved
onto_path.append(path)

rule_scores = get_rule_scores(
    f"{input_path}/interaction_rules.csv"
)
interaction_rules_sparql = create_interaction_rules_for_sparql(rule_scores)
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
        "NV": nominal,
        "tolerance": tol,
        "UL": upper,
        "LL": lower,
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
        print(f"processing.. {k}")
        # First try regex (fast + local)
        specs_output = regex_parse_spec_string(v)
        if specs_output:
            extracted_specs_dict[k] = specs_output
        else:
            extracted_specs_dict[k] = make_result()
        extracted_specs_dict[k]['id'] = f"S{spec_id + 1}"
        spec_id += 1
    with open(f"{output_path}/specs.json", "w") as f:
        json.dump(extracted_specs_dict, f, indent=2, ensure_ascii=False)
    return extracted_specs_dict

def extract_specs():
    specs_dict = {}
    df = pd.read_csv(specs_file)
    target_cols = list(df.iloc[:, [0, 1, 2]].itertuples(index=False, name=None))
    for row in target_cols:
        spec_name = row[1]
        spec_value = row[2]
        if normalize_text(spec_name.lower()) != "specification":
            specs_dict[normalize_text(spec_name.lower())] = spec_value
    #chain the process
    # specs_dict = dict(list(specs_dict.items())[:3])
    return parse_spec_strings(specs_dict)

specs = extract_specs()
#where all values are null
null_specs = {
    name.lower(): values for name, values in specs.items()
    if all(v is None for k, v in values.items() if k!= "id")
}
#non-null specs
non_null_specs = {s.lower(): v for s,v in specs.items() if s.lower() not in null_specs}

def create_failure_mode_rules():
    df = pd.read_csv(fmea_file)
    failure_modes = []
    failure_causes = []
    failure_causes_rules_mapping = {}
    target_cols = list(df.iloc[:, [0, 1, 2, 3, 4, 5, 6]].itertuples(index=False, name=None))
    # need a dictonary: defect -> [failure cause] -> [spec]
    rule_templates = {
        "less_than": '''PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/ontology/semicon-product1.owl#>
            PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
            INSERT {
                ?d base:hasFailureCause ?r .
                ?d base:violatesSpecification ?spec .
            }
            WHERE {
                ?r a base:<failure_cause> .
                ?d a base:<defect> .
                ?obs a base:<observed_spec> ;
                    base:evaluatesAgainst ?spec ;
                    base:hasObservedValue ?val ;
                    base:monitorsDefect ?d .
                ?spec base:hasLowerValue ?lower .
                FILTER(xsd:decimal(?val) < xsd:decimal(?lower))
            }''',
        "more_than": '''PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/ontology/semicon-product1.owl#>
            PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
            INSERT {
                ?d base:hasFailureCause ?r .
                ?d base:violatesSpecification ?spec .
            }
            WHERE {
                ?r a base:<failure_cause> .
                ?d a base:<defect> .
                ?obs a base:<observed_spec> ;
                    base:evaluatesAgainst ?spec ;
                    base:hasObservedValue ?val ;
                    base:monitorsDefect ?d .
                ?spec base:hasUpperValue ?upper .
                FILTER(xsd:decimal(?val) > xsd:decimal(?upper))
            }'''
    }
    fmea_data_dict = {} 
    rule_count = 0
    for row in target_cols:
        fm = row[1]
        fc = row[2]
        related_specs = [normalize_text(s.strip().lower()) for s in row[3].split(";")]
        related_specs = list(filter(lambda r: r in non_null_specs, related_specs))
        rule = row[4]
        rule_dict = parse_rule(rule)
        assert list(rule_dict.keys()) == related_specs
        if fm not in fmea_data_dict:
            failure_modes.append(fm)
            fmea_data_dict[fm] = {}
        if fc not in fmea_data_dict[fm]:
            failure_causes.append(fc)
            fmea_data_dict[fm][fc] = {
                "related_specs": related_specs,
                "rules": [],
                "severity": row[5],
                "weight": row[6],
                "id": f"FC{row[0]}"
            }
        for r in related_specs:
            for rule_obj in rule_dict[r]:
                comp = rule_obj.get("comparator")
                rule_ins = rule_templates[comp].replace(
                    "<failure_cause>", create_classname_syntax(fc)
                    ).replace(
                        "<defect>", create_classname_syntax(fm)
                    ).replace(
                        "<observed_spec>", create_classname_syntax(f"{r} obs")
                    )
                if rule_ins: rule_count += 1
                fmea_data_dict[fm][fc]['rules'].append(rule_ins)
    print(f"rule count: {rule_count}")
    failure_causes_rules_mapping = fmea_data_dict
    with open(f"{output_path}/fmea_extracts.json", "w") as f:
        json.dump(fmea_data_dict, f, indent=2, ensure_ascii=False)
    return {
        "failure_causes": failure_causes,
        "failure_modes": failure_modes,
        "failure_causes_rules_mapping": failure_causes_rules_mapping
    }

fmrs = create_failure_mode_rules()

def clean_rule(rule_str):
    cleaned = rule_str.replace("\n", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned

def define_rules(failure_causes_rules_mapping):
    rules = {}
    for defect, defect_obj in failure_causes_rules_mapping.items():
        i = 0
        for k,v in defect_obj.items():
            if k not in rules:
                rules[k] = v['rules']
                rules[k] = [clean_rule(r) for r in rules[k]]
            i+=1
    run_rules(rules, output_path)

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
    parser.add_argument("--defect-cause-matrix", action="store_true", help="generate defect cause matrix")
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
                "semicon_quality_concepts": non_null_specs,
                "failure_causes_rules_mapping": fmrs['failure_causes_rules_mapping']
            }
        )

    if args.add_specs:
        add_specs_to_ontology(
            non_null_specs,
            path
        )

    if args.add_products:
        add_products_to_ontology(
            products_in_ontology,
            f"{input_path}/synthetic_data_factory_{good_ratio}_{bad_ratio}_v{version}_{data_label}.csv",
            fmrs['failure_causes_rules_mapping'],
            non_null_specs,
            path
        )
    if args.run_rules:
        define_rules(fmrs['failure_causes_rules_mapping'])

    if args.export:
        export_ontology_to_graphdb(
            parent_ontology_path = f"{path}/semicon-base.owl",
            individual_ontology_path = f"{path}/semicon-product1.owl"
        )

    if args.defect_cause_matrix:
        generate_blind_defect_cause_matrix(
            interaction_rules_sparql,
            non_null_specs,
            fmrs['failure_causes_rules_mapping'],
            f"{output_path}/blind_dcm_{good_ratio}_{bad_ratio}_v{version}_{data_label}.csv",
            rule_interaction=False
        )

    if args.clear:
        clear_graphdb_default_graph()

    if args.evaluation_matrix:
        blind_defect_matrix = pd.read_csv(f"{output_path}/blind_dcm_{good_ratio}_{bad_ratio}_v{version}_{data_label}.csv")
        defect_matrix = pd.read_csv(f"{output_path}/dcm_{good_ratio}_{bad_ratio}_v{version}_{data_label}.csv").head(products_in_ontology)
        y_pred = blind_defect_matrix['defect']
        y_true = defect_matrix['defect']
        compute_evaluation_matrix(
            y_true,
            y_pred,
            f"{output_path}/dcm_{good_ratio}_{bad_ratio}_v{version}_EM"
        )

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

