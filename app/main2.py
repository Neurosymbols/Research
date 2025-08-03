import argparse
import pandas as pd
import json
import yaml

from scipy.stats import truncnorm, norm
from owlready2 import *
import numpy as np

from .utils import *
from .tests import *


path = "./app/data/ontologies/epoch2"
input_path = "./app/data/input/epoch2"
output_path = "./app/data/output/epoch2"
specs_file = "specs_data.csv"
output_specs_file = "specs.json"

# Set the IRIs
BASE_ONTO_IRI = "https://abakai.ai/ontology/semicon-base.owl"
PRODUCT_ONTO_IRI = "https://abakai.ai/data/semicon-product1.owl"
IOF_CORE_IRI = "https://raw.githubusercontent.com/iofoundry/ontology/master/core/Core.rdf"
BFO_IRI = "http://purl.obolibrary.org/obo/bfo.owl"

# Initialize Variables to store ontology objects in memory
base_onto = None
product1_onto = None
iof = None
bfo = None
import_iof = False

#set the path where system generated ontologies will be saved
onto_path.append(path)

#initializing failure cause concepts
failure_cause_concepts = None
df = pd.read_csv(f"{input_path}/{specs_file}")
df.columns = df.columns.str.strip()

def create_fc_concepts():
    return {
        f"FC{idx + 1}": row["Primary failure mechanism"].strip()
        for idx, row in df.iterrows()
    }
failure_cause_concepts = create_fc_concepts()

def create_semicon_quality_concepts():
    return {
        clean_param_name(row["Parameter (Xi)"]).strip(): f"S{idx + 1}"
        for idx, row in df.iterrows()
    }

semicon_quality_concepts = create_semicon_quality_concepts()

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
        fc_to_spec[fc_id] = {
            "failure_mechanism": mech,
            "parameters": params
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

# Create list of SemicON base classes
semicon_base_classes = [
'Corrective Action',
'Defect',
'Failure Cause'
]
semicon_product_class = [
   'PCB Motherboard'
]
semicon_defect_concepts = [
'Solder Bridging'
]
semicon_corrective_action_concepts = {
'CAFC1':'Stencil Thickness Correction'
}

def run_oracle():
    perform_sparql_update(
        '''
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            DELETE {
            ?defect base:flagCount ?oldCount .
            }
            INSERT {
            ?defect base:flagCount ?countTyped .
            }
            WHERE {
            {
                SELECT ?defect (xsd:integer(COUNT(?fc)) AS ?countTyped)
                WHERE {
                ?defect base:hasFailureCause ?fc .
                }
                GROUP BY ?defect
            }

            OPTIONAL {
                ?defect base:flagCount ?oldCount .
            }
            }
        '''
    )
    perform_sparql_update(
        '''
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            DELETE {
                ?defect base:interactionBonus ?oldBonus .
            }
            INSERT {
                ?defect base:interactionBonus "1"^^xsd:integer .
            }
            WHERE {
                OPTIONAL { ?defect base:interactionBonus ?oldBonus . }

                # Match all 3 FCs if present
                OPTIONAL { ?defect base:hasFailureCause product1:FC1 . }
                OPTIONAL { ?defect base:hasFailureCause product1:FC2 . }
                OPTIONAL { ?defect base:hasFailureCause product1:FC3 . }

                # Check either FC1+FC3 or FC2+FC3 present
                FILTER(
                    EXISTS { ?defect base:hasFailureCause product1:FC1 } &&
                    EXISTS { ?defect base:hasFailureCause product1:FC3 }
                    ||
                    EXISTS { ?defect base:hasFailureCause product1:FC2 } &&
                    EXISTS { ?defect base:hasFailureCause product1:FC3 }
                )
            }  
        '''
    )
    perform_sparql_update(
        '''
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            DELETE {
                ?defect base:interactionBonus ?oldBonus .
            }
            INSERT {
                ?defect base:interactionBonus "0"^^xsd:integer .
            }
            WHERE {
                OPTIONAL { ?defect base:interactionBonus ?oldBonus . }

                # Check FC1+FC3 and FC2+FC3 combinations are not present
                FILTER(
                    NOT EXISTS {
                    ?defect base:hasFailureCause product1:FC1 .
                    ?defect base:hasFailureCause product1:FC3 .
                    }
                    &&
                    NOT EXISTS {
                    ?defect base:hasFailureCause product1:FC2 .
                    ?defect base:hasFailureCause product1:FC3 .
                    }
                )
            }
        '''
    )
    perform_sparql_update(
        '''
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            DELETE {
                ?pcb base:hasDefect ?defect .
            }
            INSERT {
                ?pcb base:hasDefect ?defect .
            }
            WHERE {
                ?defect a base:SolderBridging ;
                        base:flagCount ?fc ;
                        base:interactionBonus ?ib .

                FILTER(xsd:integer(?fc) >= 2 || xsd:integer(?ib) = 1)

                ?obs base:contributesToDefect ?defect .
                ?obs base:observationOf ?pcb .

                OPTIONAL { ?pcb base:hasDefect ?defect . }
            }
        '''
    )

def create_reports():
    run_oracle()
    spec_violated_results = perform_sparql_query(
        '''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?defectLabel (COALESCE(?sp, 0) AS ?violated_spec) ?flagCount ?interaction (IF(BOUND(?pcb), "1", "0") AS ?hasDefectRelation)
            WHERE {
                ?defect a base:SolderBridging ;
                        rdfs:label ?defectLabel;
                        base:flagCount ?flagCount;
                        base:interactionBonus ?interaction


            OPTIONAL {
                ?defect base:specificationViolated ?spec .
                ?spec rdfs:label ?sp .
                
                }
            OPTIONAL {
                ?pcb base:hasDefect ?defect .
            }
            }
            ORDER BY ?defect
        '''
    )
    fc_results = perform_sparql_query(
        '''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?defectLabel (COALESCE(?fc, 0) AS ?failure_cause)
            WHERE {
                ?defect a base:SolderBridging ;
                        rdfs:label ?defectLabel;


            OPTIONAL {
                ?defect base:hasFailureCause ?failurecause .
                ?failurecause rdfs:label ?fc .
                
                }
            }
            ORDER BY ?defect
        '''
    )
    #report 1
    rows = {}
    defect_matrix_failure_causes = {}
    defect_matrix_spec_violations = {}
    blind_defect_matrix = []
    #collect violated specs per defect instance
    for row in spec_violated_results["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        if defect_label not in rows:
           rows[defect_label] = {
               'failure_causes': [], 
               'violated_specs': [],
               'flag_count': row['flagCount']['value'],
               'interaction': row['interaction']['value'],
               'defect': row['hasDefectRelation']['value']
        }
        rows[defect_label]['violated_specs'].append(row["violated_spec"]["value"])
    #collect failure causes per defect instance
    for row in fc_results["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        assert defect_label in rows, "inconsistent matrics getting formed"
        rows[defect_label]['failure_causes'].append(row["failure_cause"]["value"])
    #keys in ascending order
    rows = {k: rows[k] for k in sorted(rows.keys(), key=lambda x: int(re.search(r"PCB(\d+)", x).group(1)))}
    for defect_label in rows:
        defect_matrix_failure_causes[defect_label] = {k:1 if k in rows[defect_label]['failure_causes'] else 0 for k,v in failure_cause_concepts.items()}
    for defect_label in rows:
        defect_matrix_spec_violations[defect_label] = {k:1 if v in 
        rows[defect_label]['violated_specs'] else 0 for k,v in semicon_quality_concepts.items()}
    for k,v in defect_matrix_failure_causes.items():
        assert k in defect_matrix_spec_violations, "inconsistent matrices"
        assert k in rows, "unknown defect instance found"
        blind_defect_matrix.append({
            **defect_matrix_spec_violations[k], 
            **v, 
            "flag_count": rows[k]['flag_count'], 
            "interaction": rows[k]['interaction'],
            'defect': rows[k]['defect']
        })
    pd.DataFrame(blind_defect_matrix).to_csv(f"{output_path}/blind_defect_matrix_3.csv")

# Initiate the ontology (set create_new = true if ontologies need to be created from scratch everytime)
def initiate_ontology(create_new):
    global base_onto, product1_onto, iof, bfo
    base_onto = get_ontology(BASE_ONTO_IRI)
    product1_onto = get_ontology(PRODUCT_ONTO_IRI)
    if not create_new:
        # When ontologies exist in ontologies folder
        base_onto = base_onto.load()
        product1_onto = product1_onto.load()
    else:
        # When ontologies do not exist in ontologies folder, create them for the first time
        if import_iof:
            iof = get_ontology(IOF_CORE_IRI).load()
            bfo = get_ontology(BFO_IRI).load()
        add_base_classes() # T-Box
        add_base_individuals() # A-Box
        define_properties() # T-Box
        if import_iof:
            #idempotently import ontologies
            base_onto.imported_ontologies.append(iof) # SemicON Base Onto imports IOF
        product1_onto.imported_ontologies.append(base_onto) # Product1 Onto imports the SemicON Base Onto
        save_ontology()

def save_ontology():
    print(f"Total individuals inside SemicON Base: {len(list(base_onto.individuals()))}")
    print(f"Total individuals inside SemicON Product1: {len(list(product1_onto.individuals()))}")
    base_onto.save(file=os.path.join(path, "semicon-base.owl"), format = "rdfxml")
    product1_onto.save(file=os.path.join(path, "semicon-product1.owl"), format = "rdfxml")
    if import_iof:
        replace_iri()
  
def add_base_classes():
    #add base classes
    #T-BOX declaration
    add_classes(
       semicon_base_classes,
       Thing,
       base_onto
    )
    add_classes(
       semicon_quality_concepts,
       bfo.search_one(iri="*BFO_0000019") if import_iof else Thing,
       base_onto
    )
    add_classes(
       [f"{s} obs" for s in semicon_quality_concepts],
       iof.search_one(iri="*MeasurementInformationContentEntity") if import_iof else Thing,
       base_onto
    )
    add_classes(
        semicon_defect_concepts,
        base_onto.Defect,
        base_onto
    )
    add_classes(
        semicon_product_class,
        iof.search_one(iri="*MaterialProduct") if import_iof else Thing,
        base_onto
    )
    add_classes(
        [desc for fc, desc in failure_cause_concepts.items()],
        base_onto.FailureCause,
        base_onto
    )
    add_classes(
        [desc for ca, desc in semicon_corrective_action_concepts.items()],
        base_onto.CorrectiveAction,
        base_onto
    )

def add_base_individuals():
  #add base individuals
  # A-Box Declaration
  add_individuals(
      failure_cause_concepts,
      product1_onto,
      base_onto
  )
  add_individuals(
      semicon_corrective_action_concepts,
      product1_onto,
      base_onto
  )

def define_properties():
    with base_onto: # T-Box Declaration
        with open(f"{input_path}/ontology_properties.yml") as f:
            config = yaml.safe_load(f)
        #------------------------------ Object Properties ----------------------------------#
            for prop in config.get("object_properties", []):
                bases = [ObjectProperty]
                if prop.get("functional"):
                    bases.append(FunctionalProperty)
                cls = types.new_class(prop["name"], tuple(bases))
                if "inverse_of" in prop:
                    cls.inverse_property = base_onto[prop["inverse_of"]]
                if "domain" in prop:
                    cls.domain = [base_onto[prop["domain"]]]
                if "range" in prop:
                    cls.range = [base_onto[prop["range"]]] 

        #------------------------------ Data Properties ----------------------------------#
            for prop in config.get("data_properties", []):
                cls = types.new_class(prop["name"], (DataProperty, FunctionalProperty))
                if "domain" in prop:
                    cls.domain = [base_onto[prop["domain"]]]
                type_map = {"float": float, "int": int, "str": str}
                cls.range = [type_map[prop["range"]]]

def add_specs():
    df = pd.read_csv(f"{input_path}/{specs_file}")
    result = {}
    for _, row in df.iterrows():
        raw_param = row["Parameter (Xi)"]
        param_name = clean_param_name(raw_param)
        result[param_name] = {
            "NV": extract_number(row["Assumed process mean μ"]),
            "UL": extract_number(row["Upper spec limit (USL)"]),
            "LL": extract_number(row["Lower spec limit (LSL)"]),
            "tolerance": extract_number(row["3 σ distance†"])
        }
    with open(f"{output_path}/{output_specs_file}", "w") as f:
        json.dump(result, f, indent=2)
    with product1_onto:
        i = 1
        for si in result:
            classname = "".join([word.capitalize() for word in si.split(" ")])
            base_onto_class = base_onto[classname]
            onto_ins = base_onto_class(semicon_quality_concepts[si])
            onto_ins.label = [f"S{i}"]
            for value_type, value in result[si].items():
                if value_type == "NV":
                    onto_ins.hasNominalValue = value
                elif value_type == "LL":
                    onto_ins.hasLowerValue = value
                elif value_type == "UL":
                    onto_ins.hasUpperValue = value
            i+=1
        save_ontology()

def add_defect_individuals(batch_size:int):
   with product1_onto:
      for d in semicon_defect_concepts:
        defect_classname = create_classname_syntax(d)
        for i in range(batch_size):
           defect_individual = base_onto[defect_classname](f"{defect_classname}_PCB{i+1}")
           defect_individual.label.append(f"{defect_classname}_PCB{i+1}")


def add_products(batch_size:int):
    df = pd.read_csv(f"{input_path}/synthetic_data_factory_3.csv")
    # Strip spaces from column names
    df.columns = df.columns.str.strip() # Check specs in Synthetic Data files
    # Normalize all column names to lowercase once
    lower_cols = [col.lower() for col in df.columns]
    with product1_onto: # A-box instantiation
        for entry in semicon_quality_concepts: 
            assert entry.lower() in lower_cols, f"Column '{entry}' is missing in Synthetic data!" # check whether the 'spec' exists in synthetic data file
            values = df[entry].tolist()[0:batch_size] # get all observed values corresponding to a 'spec'. Limiting to first 20 observed values
            #create defect individuals
            add_defect_individuals(batch_size)
            PCBMotherboard = base_onto['PcbMotherboard'] # get reference to pcb motherboard class
            qual_ins = product1_onto[semicon_quality_concepts[entry]] # Get reference to the 'Quality' Individual
            for i, v in enumerate(values): # create the datastructure (i,v) list
                onto_ins = PCBMotherboard(f"PCB{i+1}") # start creating Product1 individuals
                onto_ins.label = [f"PCB{i+1}"] # assign a label
                onto_ins.hasSpecification.append(qual_ins) # connect the 'Product1' individual with 'Quality' individual using 'Semi:hasSpecification' which is not a functional property (hence using append)
                qual_observ_ins =  base_onto[f"{create_classname_syntax(entry)}Obs"](  # instantiating observed value individuals for Product1
                    f"{create_classname_syntax(entry)}_PCB{i+1}_Obs"
                    )
                qual_observ_ins.observesSpecification = qual_ins # observed value individual describes the quality individual
                qual_observ_ins.hasObservedValue = float(v) # assign hasobserved value to individual
                qual_observ_ins.observationOf = onto_ins
                for d in semicon_defect_concepts:
                   defect_ind = product1_onto[f"{create_classname_syntax(d)}_PCB{i+1}"]
                   qual_observ_ins.contributesToDefect.append(defect_ind)
                   defect_ind.flagCount = 0
                   defect_ind.interactionBonus = 0
                # onto_ins.hasObservation.append(qual_observ_ins) # connect the observed value individual to the Product1 individual
        save_ontology()
        #log the number of individuals
        print(f"{len(values)} product individuals imported to the ontology")

    return {"message": "products added"}

def add_and_run_rules():
    with product1_onto:
        rules = {
            "Thick brick slumps during reflow": [
                """
                    ThickBrickSlumpsDuringReflow(?r),
                    SolderBridging(?d),
                    StencilThicknessObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), contributesToDefect(?obs, ?d),
                    hasObservedValue(?obs, ?val), hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), specificationViolated(?d, ?spec)
                """
            ],
            "ExcessPasteVolumeCollapsesBetweenPads":[
                """
                    ExcessPasteVolumeCollapsesBetweenPads(?r),
                    SolderBridging(?d),
                    StencilApertureObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), contributesToDefect(?obs, ?d),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), specificationViolated(?d, ?spec)
                """
            ],
            "Over‑wetting enlarges solder spread":[
                """
                    OverWettingEnlargesSolderSpread(?r),
                    SolderBridging(?d),
                    PeakReflowTemperatureObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), contributesToDefect(?obs, ?d),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), specificationViolated(?d, ?spec)
                """
            ],
            "Ball straddles adjacent pads":[
                """
                    BallStraddlesAdjacentPads(?r),
                    SolderBridging(?d),
                    PlacementOffsetObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper), contributesToDefect(?obs, ?d),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), specificationViolated(?d, ?spec)
                """,
                """
                    BallStraddlesAdjacentPads(?r),
                    SolderBridging(?d),
                    PlacementOffsetObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasLowerValue(?spec, ?lower), contributesToDefect(?obs, ?d),
                    lessThan(?val, ?lower) -> hasFailureCause(?d, ?r), specificationViolated(?d, ?spec)
                """
            ],
            "Moisture‑induced flux wash‑out":[
                """
                    MoistureInducedFluxWashOut(?r),
                    SolderBridging(?d),
                    AmbientRelativeHumidityObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec), contributesToDefect(?obs, ?d),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r), specificationViolated(?d, ?spec)
                """
            ]
        }
        for rulename, rulelist in rules.items():
            for ri in rulelist:
                rule = Imp()
                rule.set_as_rule(ri, namespaces=[base_onto])
        #run rules
        t1 = time.time()
        sync_reasoner_pellet(
            infer_property_values = True, 
            infer_data_property_values = True
        )
        t2 = time.time()
        print(f"{t2-t1}s taken to run the reasoner")
        save_ontology()
    return {"message": "pellet ran successfully", "time_taken": f"{t2-t1}s"}

def generate_synthetic_data(
        N:int, 
        good_ratio:float, 
        bad_ratio:float,
        shift_std:int
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

    # Create a binary defect matrix
    defect_matrix = pd.DataFrame()
    for param, spec in specs_data.items():
        defect_matrix[param] = df_all[param].apply(
            lambda val: is_out_of_spec(val, spec["LL"], spec["UL"])
        )
    # add rules fired data to defect matrix. For now, a rule if fired if any of the contributing specs is violated
    for fc_id, fc_data in fc_to_spec.items():
        contributing_params = fc_data["parameters"]
        defect_matrix[fc_id] = defect_matrix[contributing_params].max(axis=1)

    # add interaction column
    defect_matrix["interaction"] = (
        ((defect_matrix["FC1"] == 1) & (defect_matrix["FC3"] == 1)) |
        ((defect_matrix["FC2"] == 1) & (defect_matrix["FC3"] == 1))
    ).astype(int)

    #adding and calcluating defect column
    fc_sum = defect_matrix[[col for col in defect_matrix.columns if col.startswith("FC")]].sum(axis=1)
    defect_matrix["defect"] = ((fc_sum >= 2) | (defect_matrix["interaction"] == 1)).astype(int)
    defect_matrix = defect_matrix.reset_index(drop=True)

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

    #output dataframes to csv
    df_all.to_csv(f"{input_path}/synthetic_data_factory_3.csv", index=False)
    defect_matrix.to_csv(f"{output_path}/defect_matrix_3.csv")

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
    parser.add_argument("--test", action="store_true", help="Generate synthetic data")

    args = parser.parse_args()

    if args.init:
        initiate_ontology(create_new=False)
    elif args.init_new:
        initiate_ontology(create_new=True)
    if args.add_specs:
        add_specs()
    if args.add_products:
        add_products(
            batch_size=1000
        )
    if args.run_rules:
        add_and_run_rules()
    if args.export:
        export_ontology_to_graphdb(
            parent_ontology_path = f"{path}/semicon-base.owl",
            individual_ontology_path = f"{path}/semicon-product1.owl"
        )
    if args.report:
        create_reports()
    if args.clear:
        clear_graphdb_default_graph()
    if args.generate_factory_data:
        generate_synthetic_data(
            N=10000,
            good_ratio=0.7,
            bad_ratio=0.3,
            shift_std=2
    )
    if args.test:
        blind_defect_matrix = pd.read_csv(f"{output_path}/blind_defect_matrix_3.csv")
        defect_matrix = pd.read_csv(f"{output_path}/defect_matrix_3.csv").head(1000)
        compute_evaluation_matrix(
            defect_matrix,
            blind_defect_matrix
        )

