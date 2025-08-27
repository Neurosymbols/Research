import pprint
import argparse
import owlready2
owlready2.JAVA_MEMORY = "-Xmx4g"
import pandas as pd
import numpy as np
import json

from scipy.stats import truncnorm, norm
from owlready2 import *
from .services.utils import *
from .tests import *
from .services.ontology_functions import initiate_ontology,\
    add_specs_to_ontology,\
    add_products_to_ontology,\
    run_rules
from .services.create_reports import create_reports


path = "./app/data/ontologies/epoch2"
input_path = "./app/data/input/epoch2"
output_path = "./app/data/output/epoch2"
specs_file = "specs_data.csv"
output_specs_file = "specs.json"
severity_weights_file = "severity_and_weights.csv"

#set the path where system generated ontologies will be saved
onto_path.append(path)

#initializing failure cause concepts
df = pd.read_csv(f"{input_path}/{specs_file}")
df.columns = df.columns.str.strip()

severity_df = pd.read_csv(f"{input_path}/{severity_weights_file}")
severity_df.columns = severity_df.columns.str.strip()

def create_failure_mechanism_spec_mapping():
    mapping = df[["Parameter (Xi)", "Primary failure mechanism"]].dropna()
    unique_mechs = mapping["Primary failure mechanism"].drop_duplicates().reset_index(drop=True)
    fc_map = {mech: f"FC{i+1}" for i, mech in unique_mechs.items()}
    # Add FC IDs to the dataframe
    mapping["Failure Cause ID"] = mapping["Primary failure mechanism"].map(fc_map)
    fc_to_spec = {}
    for fc_id, group in mapping.groupby("Failure Cause ID"):
        mech = group["Primary failure mechanism"].iloc[0]
        params = [clean_param_name(p) for p in group["Parameter (Xi)"].tolist()]
        severity_row = severity_df.loc[severity_df["failure mechanism"] == mech].iloc[0]
        fc_to_spec[mech] = {
            "id": fc_id,
            "parameters": params,
            "severity":int(severity_row['severity']),
            "weight": float(severity_row['weight'])
        }
    spec_to_fc = {
        clean_param_name(row["Parameter (Xi)"]): {
            "failure_cause_id": row["Failure Cause ID"],
            "failure_mechanism": row["Primary failure mechanism"]
        }
        for _, row in mapping.iterrows()
    }
    with open(f"{input_path}/failure_cause_mapping.json", "w") as f:
        json.dump(fc_to_spec, f, indent=2)
    with open(f"{input_path}/parameter_to_failure_mapping.json", "w") as f:
        json.dump(spec_to_fc, f, indent=2)
    return fc_to_spec

fc_to_spec = create_failure_mechanism_spec_mapping()
failure_causes_rules_mapping = {}
semicon_defect_concepts = [
    'Solder Bridging'
]
for fm in semicon_defect_concepts:
    if fm not in failure_causes_rules_mapping:
        failure_causes_rules_mapping[fm] = fc_to_spec

semicon_corrective_action_concepts = {
'CAFC1':'Stencil Thickness Correction'
}
rule_scores = {
    ("FC1", "FC2"): 3,
    ("FC1", "FC3"): 2,
    ("FC1", "FC2", "FC3"): 4
}

interaction_rules_sparql = create_interaction_rules_for_sparql(rule_scores)

def extract_specs():
    df = pd.read_csv(f"{input_path}/{specs_file}")
    result = {}
    spec_id = 0
    for _, row in df.iterrows():
        raw_param = row["Parameter (Xi)"]
        result[clean_param_name(raw_param)] = {
            "NV": extract_number(row["Assumed process mean μ"]),
            "UL": extract_number(row["Upper spec limit (USL)"]),
            "LL": extract_number(row["Lower spec limit (LSL)"]),
            "tolerance": extract_number(row["3 σ distance†"]),
            "id": f"S{spec_id + 1}"
        }
        spec_id += 1
    with open(f"{output_path}/{output_specs_file}", "w") as f:
        json.dump(result, f, indent=2)
    return result
    # add_specs_to_ontology(result, path)

specs = extract_specs()

def define_rules():
    rules = {
        "Thick brick slumps during reflow": [
            """
                ThickBrickSlumpsDuringReflow(?r),
                SolderBridging(?d),
                StencilThicknessObs(?obs),
                observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), monitorsDefect(?obs, ?d),
                hasObservedValue(?obs, ?val), hasUpperValue(?spec, ?upper),
                greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), violatesSpecification(?d, ?spec)
            """
        ],
        "ExcessPasteVolumeCollapsesBetweenPads":[
            """
                ExcessPasteVolumeCollapsesBetweenPads(?r),
                SolderBridging(?d),
                StencilApertureObs(?obs),
                observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), monitorsDefect(?obs, ?d),
                hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), violatesSpecification(?d, ?spec)
            """
        ],
        "Over‑wetting enlarges solder spread":[
            """
                OverWettingEnlargesSolderSpread(?r),
                SolderBridging(?d),
                PeakReflowTemperatureObs(?obs),
                observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), monitorsDefect(?obs, ?d),
                hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), violatesSpecification(?d, ?spec)
            """
        ],
        "Ball straddles adjacent pads":[
            """
                BallStraddlesAdjacentPads(?r),
                SolderBridging(?d),
                PlacementOffsetObs(?obs),
                observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper), monitorsDefect(?obs, ?d),
                greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), violatesSpecification(?d, ?spec)
            """,
            """
                BallStraddlesAdjacentPads(?r),
                SolderBridging(?d),
                PlacementOffsetObs(?obs),
                observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                hasObservedValue(?obs, ?val),hasLowerValue(?spec, ?lower), monitorsDefect(?obs, ?d),
                lessThan(?val, ?lower) -> hasFailureCause(?d, ?r), violatesSpecification(?d, ?spec)
            """
        ],
        "Moisture‑induced flux wash‑out":[
            """
                MoistureInducedFluxWashOut(?r),
                SolderBridging(?d),
                AmbientRelativeHumidityObs(?obs),
                observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), monitorsDefect(?obs, ?d),
                hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), violatesSpecification(?d, ?spec)
            """
        ]
    }
    run_rules(
        rules,
        path
    )

def generate_synthetic_data(
        N:int, 
        good_ratio:float, 
        bad_ratio:float,
        shift_std:int,
        generate_data=True
    ):
    with open(f"{output_path}/{output_specs_file}", "r") as f:
        specs_data = json.load(f)
    def truncated_normal(mu, sigma, low, high, size):
        #calculate a and b to truncate the normal distribution between LSL and USL. This ensures the samples stay within spec limits → good panels.
        a, b = (low - mu)/sigma, (high - mu)/sigma
        return truncnorm(a, b, loc=mu, scale=sigma).rvs(size) #represents normal distribution N(μ, σ)
    def shifted_normal(mu, sigma, shift_std, size):
        return norm.rvs(loc=mu + shift_std * sigma, scale=sigma, size=size)
    def is_out_of_spec(value, lower, upper):
        if lower is not None and value < lower:
            return 1
        if upper is not None and value > upper:
            return 1
        return 0
    # Apply rule-based labeling
    def assign_label(row, spec_dict):
        for col, spec in spec_dict.items():
            value = row[col]
            if is_out_of_spec(value, spec["LL"], spec["UL"]):
                return 1  # out of spec → defect
        return 0  # in spec → no defect
    
    df_all = None
    if generate_data:
        good_samples = {}
        bad_samples = {}
        for param, vals in specs_data.items():
            mu = vals["NV"]
            sigma = vals["tolerance"] / 3  # Assuming 3σ range
            LSL = vals["LL"] if vals["LL"] is not None else mu - (3 * sigma)
            USL = vals["UL"] if vals["UL"] is not None else mu + (3 * sigma)

            good_samples[param] = truncated_normal(mu, sigma, LSL, USL, int(N * good_ratio))
            bad_samples[param] = shifted_normal(mu, sigma, shift_std, int(N * bad_ratio))
        
        # Create DataFrames
        df_good_panels = pd.DataFrame(good_samples)
        df_bad_panels = pd.DataFrame(bad_samples)
        # Combine and shuffle
        df_all = pd.concat([df_good_panels, df_bad_panels]).sample(frac=1).reset_index(drop=True)

        df_all["label"] = df_all.apply(lambda row: assign_label(row, specs_data), axis=1)

        # Move 'label' column to the front
        cols = ['label'] + [col for col in df_all.columns if col != 'label']
        df_all = df_all[cols]
        #output dataframes to csv
        df_all.to_csv(f"{input_path}/synthetic_data_factory.csv", index=False)
    else:
        print("hello world")
        df_all = pd.read_csv(f"{input_path}/synthetic_data_factory.csv")

    # Create a binary defect matrix
    defect_matrix = pd.DataFrame()
    for param, spec in specs_data.items():
        defect_matrix[param] = df_all[param].apply(
            lambda val: is_out_of_spec(val, spec["LL"], spec["UL"])
        )

    # add rules fired data to defect matrix. For now, a rule if fired if any of the contributing specs is violated
    defect_matrix['rbi_score'] = 0
    for fc_id, fc_data in fc_to_spec.items():
        contributing_params = fc_data["parameters"]
        defect_matrix[fc_id] = defect_matrix[contributing_params].max(axis=1)
        defect_matrix['rbi_score'] += defect_matrix[fc_id] * fc_data['weight'] * fc_data['severity']
    
    # add interaction column
    # Initialize interaction column with 0
    # Sum all matching rules (stacking)
    defect_matrix["interaction"] = 0
    for rule_tuple, score in rule_scores.items():
        mask = defect_matrix[list(rule_tuple)].eq(1).all(axis=1)
        defect_matrix.loc[mask, "interaction"] += score
    #adding interaction bonus to rbi score
    defect_matrix['rbi_score'] += defect_matrix['interaction']

    #adding and calcluating defect and flag count column
    defect_matrix["fc_count"] = 0
    fc_sum = defect_matrix[[col for col in defect_matrix.columns if col.startswith("FC")]].sum(axis=1)
    defect_matrix['fc_count'] = fc_sum
    # its a solder bridging if rules fired are >=2 OR interaction == 1
    defect_matrix["defect"] = ((fc_sum >= 2) | (defect_matrix["interaction"] > 1)).astype(int)
    defect_matrix = defect_matrix.reset_index(drop=True)

    if generate_data:
        # 1. Length of good and bad samples
        num_good = len(df_good_panels)
        num_bad = len(df_bad_panels)

        # 2. Total rows
        total_rows = num_good + num_bad

        # 3. Number of actual failures based on spec checks
        num_failures = defect_matrix["defect"].sum()

        # 4. Calculate percentage of defect rows
        failure_percentage = (num_failures / total_rows) * 100

        # 5. Print
        print("✅ Number of good samples:", num_good)
        print("⚠️ Number of bad samples:", num_bad)
        print(f"❌ Number of labeled defects: {num_failures} ({failure_percentage:.2f}%)")

    defect_matrix.to_csv(f"{output_path}/defect_cause_matrix.csv")

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
    parser.add_argument("--generate-factory-data", action="store_true", help="Generate synthetic data")
    parser.add_argument("--evaluation-matrix", action="store_true", help="Generate synthetic data")
    parser.add_argument("--root-cause", action="store_true", help="Generate synthetic data")

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
                "semicon_quality_concepts": specs,
                "failure_causes_rules_mapping": failure_causes_rules_mapping
            }
        )
    if args.add_specs:
        add_specs_to_ontology(
            specs,
            path
        )
    if args.add_products:
        add_products_to_ontology(
            5000,
            f"{input_path}/synthetic_data_factory.csv",
            failure_causes_rules_mapping,
            specs,
            path
        )
    if args.run_rules:
        define_rules()
    if args.export:
        export_ontology_to_graphdb(
            parent_ontology_path = f"{path}/semicon-base.owl",
            individual_ontology_path = f"{path}/semicon-product1.owl"
        )
    if args.report:
        create_reports(
            interaction_rules_sparql,
            specs,
            failure_causes_rules_mapping,
            f"{output_path}/blind_defect_cause_matrix.csv"
        )
    if args.clear:
        clear_graphdb_default_graph()
    if args.generate_factory_data:
        generate_synthetic_data(
            50000,
            0.7,
            0.3,
            2,
            generate_data=False
    )
    if args.evaluation_matrix:
        blind_defect_matrix = pd.read_csv(f"{output_path}/blind_defect_cause_matrix.csv")
        defect_matrix = pd.read_csv(f"{output_path}/defect_cause_matrix.csv").head(5000)
        y_pred = blind_defect_matrix['defect']
        y_true = defect_matrix['defect']
        compute_evaluation_matrix(
            y_true,
            y_pred
        )
    if args.root_cause:
        #TODO: generate sparql report for now showing RCA
        pass

