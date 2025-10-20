import argparse
import json
import os
import numpy as np
import pandas as pd

from decimal import Decimal, ROUND_HALF_UP
from owlready2 import *
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain.prompts import ChatPromptTemplate
from scipy.stats import truncnorm, norm, gaussian_kde, halfnorm

from app.services.utils import *
from .services.ontology_functions import initiate_ontology,\
    add_specs_to_ontology,\
    add_products_to_ontology,\
    run_rules
from .services.create_reports import create_reports
from .services.bayesian_inference import implement_bayesian_inference
from .tests import *


GEMINI_API_KEY = "AIzaSyAlP3WbsB0VqdVEnZ-_Dw22C5XcW51Uvcg"
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

path = "./app/data/ontologies/epoch3-6"
input_path = f"./app/data/input/epoch3-6"
output_path = f"./app/data/output/epoch3-6"
specs_file = f"{input_path}/specs_data_sp.csv"
fmea_file = f"{input_path}/fmea-sp.csv"

#set the path where system generated ontologies will be saved
onto_path.append(path)
# llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
llm = ChatOllama(model="llama3")

rule_scores = get_rule_scores(
    f"{input_path}/interaction_rules.csv"
)
interaction_rules_sparql = create_interaction_rules_for_sparql(rule_scores)
good_ratio = 0.5
bad_ratio = 0.5
version = 3
products_in_ontology = 1000
products_in_synthetic_data = 1000
data_label = "test"
defect_threshold = 0.55

def normalize_text(text: str) -> str:
    # Replace all unicode whitespace (incl. \u202f, \u00a0, etc.) with plain space
    return re.sub(r"\s+", " ", text, flags=re.UNICODE).strip()

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

def regex_parse(spec: str):
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
    response_schemas = [
        ResponseSchema(name="nominal_value", description="Nominal value as number or null"),
        ResponseSchema(name="tolerance", description="Tolerance as number or null"),
        ResponseSchema(name="upper_value", description="Upper bound as number or null"),
        ResponseSchema(name="lower_value", description="Lower bound as number or null"),
        ResponseSchema(name="units", description="Units of measurement or null"),
    ]
    parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = parser.get_format_instructions()
    prompt = ChatPromptTemplate.from_template("""
        You are a parser. Extract specification details from the string.

        Spec string: {spec}

        {format_instructions}
        """
    )
    extracted_specs_dict = {}
    spec_id = 0
    for k, v in specs_dict.items():
        print(f"processing.. {k}")
        # First try regex (fast + local)
        specs_output = regex_parse(v)
        if specs_output:
            extracted_specs_dict[k] = specs_output
        else:
            try:
                print("in llm")
                llm_chain = prompt | llm | parser
                specs_output = llm_chain.invoke({"spec": v, "format_instructions": format_instructions})
                extracted_specs_dict[k] = specs_output
            except Exception:
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

def extract_param_directions(expr: str):
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
                    base:observesSpecification ?spec ;
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
                    base:observesSpecification ?spec ;
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
        target_specs = extract_param_directions(row[4])
        rule = row[4]
        rule_dict = parse_rule(rule)
        if fm not in fmea_data_dict:
            failure_modes.append(fm)
            fmea_data_dict[fm] = {}
        if fc not in fmea_data_dict[fm]:
            failure_causes.append(fc)
            fmea_data_dict[fm][fc] = {
                "related_specs": related_specs, 
                "target_specs": target_specs,
                "rules": [],
                "severity": row[5],
                "weight": row[6],
                "id": f"FC{row[0]}"
            }
        for r in related_specs:
            if r in rule_dict and r in non_null_specs and r not in null_specs:
                for rule_obj in rule_dict[r]:
                    comp = rule_obj.get("comparator")
                    rule_ins = rule_templates[comp].replace(
                        "<failure_cause>", create_classname_syntax(fc)
                        ).replace(
                            "<defect>", create_classname_syntax(fm)
                        ).replace(
                            "<observed_spec>", create_classname_syntax(f"{r} obs")
                        )
                    if rule_ins:
                        rule_count += 1
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

def add_interaction_bonus(defect_matrix:pd.DataFrame, interaction_flag):
    if interaction_flag:
        # add interaction column
        # Initialize interaction column with 0
        # Sum all matching rules (stacking)
        defect_matrix["interaction"] = 0
        defect_matrix["interactions_occured"] = "" 
        for rule_tuple, score in rule_scores.items():
            #marking the rows in dataframe where value of FC's inside given rule tuple > 0
            mask = (defect_matrix[list(rule_tuple)] > 0).all(axis=1)
            #go to thos row locatons and update interaction bonus cumulatively
            defect_matrix.loc[mask, "interaction"] += score
            # add tuple name(s) to string column
            defect_matrix.loc[mask, "interactions_occured"] = defect_matrix.loc[mask, "interactions_occured"].apply(
                lambda x: (x + " " + str(rule_tuple)).strip()
            )
        #adding interaction bonus to rbi score
        defect_matrix['rbi_score'] += defect_matrix['interaction']
    else:
        defect_matrix["interaction"] = 0

def ground_truth_algorithm(
        defect_matrix:pd.DataFrame, 
        threshold:float = None,
        threshold_column:float = "rbi_score"
    ):
    def manual_percentile(data, q):
        """
        Manual percentile calculation with interpolation.
        data: list or array
        q: percentile (0-100)
        """
        data = np.sort(data)                 # 1. sort values
        N = len(data)
        
        pos = (q/100) * (N - 1)              # 2. position
        lower = int(np.floor(pos))           # 3. lower index
        upper = int(np.ceil(pos))            # 4. upper index
        weight = pos - lower                 # 5. interpolation weight

        if lower == upper:                   # exact position
            return data[lower]
        else:                                # interpolate
            return data[lower] * (1-weight) + data[upper] * weight
    # compute threshold T: percentile on RBI scores of bad samples
    def generate_threshold(rbi_scores:list):
        #defect_pct points to defect prevalence percentage. Assuming desired defect_pct to be ~50% of the bad samples
        #None of the good samples is defective
        #Right now each one of the bad samples is defective due to which we are not able to get the desired defect prevalence percentage. Bad samples need to be a mix of defective and non-defective. Defective ones should account for desired defect prevalence percentage in the overall set.
        #calculate no of defective samples
        defect_pct = 0.5 * bad_ratio
        defective_samples = defect_pct * N
        percent_of_bad = defective_samples / int(N * bad_ratio)
        print(f"percent of bad: {percent_of_bad}")
        return manual_percentile(rbi_scores, 100 * (1 - percent_of_bad))
        # return np.percentile(rbi_scores, 100 * (1 - defect_pct))
    
    if not threshold:
        # its a possible solder bridging if rules fired are >=2 OR interaction == 1
        if "interaction" in defect_matrix.columns:
            defect_matrix["defect"] = ((defect_matrix['fc_count'] >= 2) | (defect_matrix["interaction"] > 1)).astype(int)
        else:
            defect_matrix["defect"] = ((defect_matrix['fc_count'] >= 2)).astype(int)
        # perform overlap of bad samples with good samples using rbi score theresold T
        rbi_scores_bad_samples = defect_matrix.loc[defect_matrix["defect"] == 1, "rbi_score"].values
        threshold = generate_threshold(rbi_scores_bad_samples)
        print(f"threshold: {threshold}")
    defect_matrix["defect"] = (defect_matrix[threshold_column] >= threshold).astype(int)
    return threshold

def generate_defect_cause_matrix(
    good_ratio:float, 
    bad_ratio:float,
    version:int = 1,
    label:str="train",
    data_matrix:pd.DataFrame = None,
    output:bool=False
):
    def is_out_of_spec(given_spec, values: pd.Series, spec_data, target_specs):
        """Return a Series of 1/0 flags for a spec column."""
        if given_spec not in target_specs:
            return pd.Series(0, index=values.index)

        directions = target_specs[given_spec]
        # start with all 0s
        result = pd.Series(0, index=values.index)

        for direction in directions:
            if direction == "UL" and spec_data.get("UL") is not None:
                result = result | (values > spec_data["UL"]).astype(int)
            elif direction == "LL" and spec_data.get("LL") is not None:
                result = result | (values < spec_data["LL"]).astype(int)

        return result
    if not data_matrix:
        data_matrix = pd.read_csv(f"{input_path}/synthetic_data_factory_{good_ratio}_{bad_ratio}_v{version}_{label}.csv")
    #include non-null specs inside specs_data
    specs_data = {k:v for k,v in specs.items() if k in non_null_specs}
    # Create a binary defect cause matrix
    defect_matrix = pd.DataFrame(0, index=data_matrix.index, columns=['rbi_score'])
    # add rules fired data to defect matrix. For now, a rule if fired if any of the contributing specs is violated
    defect_matrix['rbi_score'] = 0
    for defect, defect_info in fmrs['failure_causes_rules_mapping'].items():
        for fc_name, fc_data in defect_info.items():
            contributing_params = [r for r in fc_data["related_specs"] if r in non_null_specs and r not in null_specs ]
            target_params = fc_data['target_specs']
            union_flags = pd.Series(0, index=data_matrix.index)
            for p in contributing_params:
                if p in target_params:
                    flags = is_out_of_spec(p, data_matrix[p], specs_data[p], target_params)
                    # union = logical OR (max)
                    union_flags = union_flags.combine(flags, max)
            weighted = union_flags * fc_data['weight'] * fc_data['severity']
            defect_matrix[fc_data['id']] = weighted
            defect_matrix['rbi_score'] += weighted
    # get all FC columns
    fc_cols = [c for c in defect_matrix.columns if c.startswith("FC")]
    # create new column with joined FC names where value == 1
    defect_matrix["rules_fired"] = defect_matrix.apply(
        lambda row: ",".join([col for col in fc_cols if row[col] >0]),
        axis=1
    )
    #adding and calcluating defect and flag count column
    defect_matrix['fc_count'] = (defect_matrix[fc_cols] > 0).sum(axis=1)
    if "defect probability" in data_matrix.columns:
        defect_matrix['defect probability'] = data_matrix['defect probability']
    if output:
        defect_matrix.to_csv(f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_{label}.csv")
    return defect_matrix

def generate_synthetic_data(
        N:int, 
        good_ratio:float, 
        bad_ratio:float,
        shift_std:int,
        generate_data=True,
        rule_interaction=False,
        version:int = 1,
        label:str="train"
    ):

    def truncated_normal(mu, sigma, low, high, size):
        #calculate a and b to truncate the normal distribution between LSL and USL. This ensures the samples stay within spec limits → good panels.
        a, b = (low - mu)/sigma, (high - mu)/sigma
        return truncnorm(a, b, loc=mu, scale=sigma).rvs(size) #represents normal distribution N(μ, σ)
    def shifted_normal(mu, sigma, shift_std, size):
        return norm.rvs(loc=mu + shift_std * sigma, scale=sigma, size=size)
    ################
    #TODO: audit the defect generation formulas for one sided specs
    ################
    def half_normal(bound, sigma, size, bound_type, good=True):
        if bound_type == "upper":
            if good:
                #sigma=0.2
                return bound - halfnorm.rvs(scale=sigma, size=size)
            else:
                return bound + halfnorm.rvs(scale=sigma, size=size)
        elif bound_type == "lower":
            if good:
                return bound + halfnorm.rvs(scale=sigma, size=size)
            else:
                return bound - halfnorm.rvs(scale=sigma, size=size)
    df_all = None
    #include non-null specs inside specs_data
    specs_data = {k:v for k,v in specs.items() if k in non_null_specs}
    if generate_data:
        good_samples = {}
        bad_samples = {}
        for param, vals in specs_data.items():
            if vals['NV'] is not None and vals['tolerance']:
                mu = vals["NV"]
                sigma = vals["tolerance"] / 3  # Assuming 3σ range
                LSL = vals["LL"] if vals["LL"] is not None else mu - (3 * sigma)
                USL = vals["UL"] if vals["UL"] is not None else mu + (3 * sigma)

                good_samples[param] = truncated_normal(mu, sigma, LSL, USL, int(N * good_ratio))
                bad_samples[param] = shifted_normal(mu, sigma, shift_std, int(N * bad_ratio))
            elif not vals['NV'] and not vals['tolerance']:
                if vals['UL']:
                    good_samples[param] = half_normal(vals['UL'], 0.2, int(N * good_ratio), 'upper', True)
                    bad_samples[param] = half_normal(vals['UL'], 0.2, int(N * bad_ratio), 'upper', False)
                elif vals['LL']:
                    good_samples[param] = half_normal(vals['LL'], 0.2, int(N * good_ratio), 'lower', True)
                    bad_samples[param] = half_normal(vals['LL'], 0.2, int(N * bad_ratio), 'lower', False)
            elif vals['NV'] is not None and vals['tolerance'] == 0.0:
                # Case: zero tolerance → deterministic samples
                good_samples[param] = [mu] * int(N * good_ratio)
                bad_samples[param] = [mu] * int(N * bad_ratio)

        # Create DataFrames
        df_good_panels = pd.DataFrame(good_samples)
        df_bad_panels = pd.DataFrame(bad_samples)
        # Combine and shuffle
        df_all = pd.concat([df_good_panels, df_bad_panels]).sample(frac=1).reset_index(drop=True)

        #output dataframes to csv
        df_all.to_csv(f"{input_path}/synthetic_data_factory_{good_ratio}_{bad_ratio}_v{version}_{label}.csv", index=False)
    else:
        df_all = pd.read_csv(f"{input_path}/synthetic_data_factory_{good_ratio}_{bad_ratio}_v{version}_{label}.csv")
    
    defect_matrix = generate_defect_cause_matrix(data_matrix=df_all)

    add_interaction_bonus(defect_matrix, rule_interaction)

    threshold = ground_truth_algorithm(defect_matrix)

    defect_matrix = defect_matrix.reset_index(drop=True)

    # 1. Length of defective samples after threshold
    num_bad = defect_matrix["defect"].value_counts().get(1, 0)
    # 2. Calculate percentage of defect rows
    failure_percentage = (num_bad / defect_matrix.shape[0]) * 100
    # 3. Print
    print("✅ Number of good samples:", int(N * good_ratio))
    print("⚠️ Number of bad samples:", int(N * bad_ratio))
    print(f"❌ Number of labeled defects: {num_bad} ({failure_percentage:.2f}%)")

    #update thresholds
    try:
        thresholds_df = pd.read_csv(f"{output_path}/thresholds.csv")
        if "Unnamed: 0" in thresholds_df.columns:
            thresholds_df = thresholds_df.drop(columns=["Unnamed: 0"])
    except pd.errors.EmptyDataError:
        header = ['factory_data_version', 'rbi_threshold', 'rule_interaction', 'total_products']
        thresholds_df = pd.DataFrame(columns=header)
    # Define the new row (dict for clarity)
    new_row = {
        "factory_data_version": f"{good_ratio}_{bad_ratio}_v{version}_{N}",
        "rbi_threshold": float(threshold),
        "rule_interaction": rule_interaction,
        "total_products": N,
    }

    # Check if factory_data_version already exists
    mask = thresholds_df["factory_data_version"] == new_row["factory_data_version"]

    if mask.any():
        # Update existing row
        thresholds_df.loc[mask, :] = pd.DataFrame([new_row])
    else:
        # Append new row
        thresholds_df = pd.concat([thresholds_df, pd.DataFrame([new_row])], ignore_index=True)
    thresholds_df.to_csv(f"{output_path}/thresholds.csv")
    defect_matrix.to_csv(f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_{label}.csv")

if __name__ == "__main__":
    rbi_threshold = None
    try:
        tdf = pd.read_csv(f"{output_path}/thresholds.csv")
        print(tdf['factory_data_version'].tolist())
        result = tdf.loc[tdf["factory_data_version"] == f"{good_ratio}_{bad_ratio}_v{version}_{products_in_synthetic_data}", "rbi_threshold"]
        if result.to_list():
            rbi_threshold = result.tolist()[0]
    except pd.errors.EmptyDataError as e:
        print(e)

    parser = argparse.ArgumentParser(description="SemicON Ontology CLI")

    parser.add_argument("--init", action="store_true", help="Initiate ontology (create_new=False)")
    parser.add_argument("--init-new", action="store_true", help="Initiate ontology (create_new=True)")
    parser.add_argument("--add-specs", action="store_true", help="Add specifications")
    parser.add_argument("--add-products", action="store_true", help="Add products")
    parser.add_argument("--run-rules", action="store_true", help="Add and run SWRL rules")
    parser.add_argument("--export", action="store_true", help="Export ontology to GraphDB")
    parser.add_argument("--report", action="store_true", help="Generate failure reports")
    parser.add_argument("--clear", action="store_true", help="Clear the default graph in GraphDB")
    parser.add_argument("--generate-factory-data", action="store_true", help="Generate synthetic data")
    parser.add_argument("--evaluation-matrix", action="store_true", help="Generate evaluation matrix")
    parser.add_argument("--root-cause", action="store_true", help="Find root cause of failure mode")
    parser.add_argument("--implement-bayes-inf", action="store_true", help="Implement bayesian inference")
    parser.add_argument("--generate-defect-cause-matrix", action="store_true", help="generate defect cause matrix")

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
    if args.report:
        create_reports(
            interaction_rules_sparql,
            non_null_specs,
            fmrs['failure_causes_rules_mapping'],
            f"{output_path}/blind_defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}.csv",
            rule_interaction=False,
            rbi_threshold=rbi_threshold
        )
    if args.clear:
        clear_graphdb_default_graph()
    if args.generate_factory_data:
        generate_synthetic_data(
            products_in_synthetic_data,
            good_ratio,
            bad_ratio,
            2,
            generate_data=True,
            rule_interaction=False,
            version=version,
            label = data_label
    )
    if args.evaluation_matrix:
        blind_defect_matrix = pd.read_csv(f"{output_path}/blind_defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}.csv")
        defect_matrix = pd.read_csv(f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_{data_label}.csv").head(products_in_ontology)
        y_pred = blind_defect_matrix['defect']
        y_true = defect_matrix['defect']
        compute_evaluation_matrix(
            y_true,
            y_pred,
            f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_EM"
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
    if args.generate_defect_cause_matrix:
        defect_matrix = generate_defect_cause_matrix(
            good_ratio,
            bad_ratio,
            version,
            label = data_label,
            output = False
        )
        ground_truth_algorithm(
            defect_matrix,
            defect_threshold,
            "defect probability"
        )
        defect_matrix.to_csv(f"{output_path}/defect_cause_matrix_{good_ratio}_{bad_ratio}_v{version}_{data_label}.csv")

