# CONFIDENTIAL 
# Copyright Abakai

import argparse
import os
import types
import math
import json
import pandas as pd
import re

from owlready2 import *
from app.services.graphdb_ops import perform_sparql_query, export_ontology_to_graphdb, clear_graphdb_default_graph

path = "./app/data/ontologies"
input_path = "./app/data/input"
output_path = "./app/data/output"

#set the path where system generated ontologies will be saved
onto_path.append(path)

# Set the IRIs
BASE_ONTO_IRI = "https://abakai.ai/ontology/semicon-base.owl"
PRODUCT_ONTO_IRI = "https://abakai.ai/data/semicon-product1.owl"

# Initialize Variables to store ontology objects in memory
base_onto = None
product1_onto = None

# Create list of SemicON base classes
semicon_base_classes = [
'Corrective Action',
'Defect',
'Failure Cause',
'Pcb Motherboard',
'Quality',
'Observed Quality'
]

semicon_quality_concepts = [
'Stencil Thickness',
'Residual Paste Allowed',
'Paste volume per aperture',
'Squeegee pressure',
'Squeegee speed',
'Squeegee angle',
]

semicon_defect_concepts = [
'Solder Bridging',
'Open Solder Joint'
]

failure_cause_concepts = {
'FC1':'Oversized stencil aperture or excessive overprint',
'FC2':'Excess squeegee pressure',
'FC3':'Stencil thickness too high',
'FC4':'Insufficient squeegee pressure',
'FC5':'Excess squeegee speed',
'FC6':'Squeegee angle out of spec',
'FC7':'Residual paste left on stencil edge'
}

semicon_corrective_action_concepts = {
'CAFC1':'Stencil Thickness Correction'
}

def create_reports():
    results = perform_sparql_query(
        query = '''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?productLabel (COALESCE(?desc, "No Failure Cause") AS ?failure_cause)
            WHERE {
                ?product a base:PcbMotherboard ;
                        rdfs:label ?productLabel;
                        

                OPTIONAL {
                    ?product base:hasFailureCause ?failurecause .
                    ?failurecause rdfs:label ?desc .
                }
            }
            ORDER BY ?product
        '''
    )
    # 1) Group all failure-cause IDs by product
    #    Example: grouped["PCB1"] = set(["FC1", "FC3", ...])
    grouped = defaultdict(set)
    for row in results["results"]["bindings"]:
        product = row["productLabel"]["value"]
        fc_id   = row["failure_cause"]["value"]
        grouped[product].add(fc_id)
    
    # 2) Sort products by the number that appears after the first 3 characters.
    #    Original code did: int(product[3:])
    #    This helper keeps it robust if a name doesn’t match that pattern.
    def product_sort_key(name: str) -> int:
        try:
            return int(name[3:])
        except (ValueError, IndexError):
            return float('inf')  # push odd names to the end

    products_sorted = sorted(grouped.keys(), key=product_sort_key)

    # 3) Build the report rows.
    #    For each product, list every known failure cause (from failure_cause_concepts).
    #    Put the product name on the first line, then leave it blank for the rest
    #    so it reads nicely in the CSV.
    rows_for_csv = []
    for product in products_sorted:
        seen_fc_ids = grouped[product]
        first_line_for_product = True

        for fc_id, fc_desc in failure_cause_concepts.items():
            rows_for_csv.append({
                "Product": product if first_line_for_product else "",
                "Failure Cause": fc_desc,                  # human-friendly text
                "Variable": 1 if fc_id in seen_fc_ids else 0  # 1 = fired, 0 = not fired
            })
            first_line_for_product = False
    
    pd.DataFrame(rows_for_csv).to_csv(f"{output_path}/rule_firing_report.csv", index=False)

def extract_floats(s):
    # Match optional sign, digits, optional decimal part
    return [float(num) for num in re.findall(r'[-+]?\d*\.\d+|[-+]?\d+', s)]

def sum_nos(arr):
    total = math.fsum(arr)
    max_dp = 0
    for v in arr:
        s = str(v)
        if '.' in s:
            dp = len(s.split('.')[1])
            if dp > max_dp:
                max_dp = dp
    return round(total, max_dp)

def get_spec_values(v:str):
    specs = {"NV": 0.0, "UL": 0.0, "LL": 0.0}
    comp_signs = ["<", ">", "≥"]
    comp_sign_pat = "|".join(map(re.escape, comp_signs))
    if "±" in v:
        floats = extract_floats(v)
        specs['NV'] = floats[0]
        specs['UL'] = sum_nos(floats)
        specs['LL'] = sum_nos([floats[0], -floats[1]])
        specs['tolerance'] = floats[1]
    if re.search(comp_sign_pat, v):
        floats = extract_floats(v)
        specs['NV'] = floats[0]
    return specs

# Initiate the ontology (set create_new = true if ontologies need to be created from scratch everytime)
def initiate_ontology(create_new):
    global base_onto, product1_onto
    base_onto = get_ontology(BASE_ONTO_IRI)
    product1_onto = get_ontology(PRODUCT_ONTO_IRI)
    if not create_new:
        # When ontologies exist in ontologies folder
        base_onto = base_onto.load()
        product1_onto = product1_onto.load()
    else:
        # When ontologies do not exist in ontologies folder, create them for the first time
        add_base_classes() # T-Box
        add_base_individuals() # A-Box
        define_properties() # T-Box
        save_ontology()

def save_ontology():
    print(f"Total individuals inside SemicON Base: {len(list(base_onto.individuals()))}")
    print(f"Total individuals inside SemicON Product1: {len(list(product1_onto.individuals()))}")
    base_onto.save(file=os.path.join(path, "semicon-base.owl"), format = "rdfxml")
    product1_onto.save(file=os.path.join(path, "semicon-product1.owl"), format = "rdfxml")

def get_ontology_classname(string):
    return "".join([word.capitalize() for word in string.split(" ")]) # CamelCase compliance

def add_base_classes():
  #add base classes
  #follow CamelCase compliance while creating ontology classes
  with base_onto: # T-Box Declaration
    for classname in semicon_base_classes:
      base_class = types.new_class(get_ontology_classname(classname), (Thing,))
      base_class.label.append(classname)
    for classname in semicon_quality_concepts:
      quality_class = types.new_class(get_ontology_classname(classname), (base_onto.Quality,))
      quality_obs_class = types.new_class(get_ontology_classname(f"{classname} Obs"), (base_onto.ObservedQuality,))
      quality_class.label.append(classname)
      quality_obs_class.label.append(f"{classname} Obs")
    for classname in semicon_defect_concepts:
      defect_class = types.new_class(get_ontology_classname(classname), (base_onto.Defect,))
      defect_class.label.append(classname)
    for fc, desc in failure_cause_concepts.items():
      fc_class = types.new_class(get_ontology_classname(desc), (base_onto.FailureCause,))
      fc_class.label.append(desc)
    for ca, desc in semicon_corrective_action_concepts.items():
      ca_class = types.new_class(get_ontology_classname(desc), (base_onto.CorrectiveAction,))
      ca_class.label.append(desc)

def add_base_individuals():
  #add base individuals
  with product1_onto: # A-Box Declaration
    for fc, desc in failure_cause_concepts.items():
      #add failure cause individual
      fci = base_onto[get_ontology_classname(desc)](fc)
      fci.label.append(fc)
    for ca, desc in semicon_corrective_action_concepts.items():
      #add corrective action individual
      cai = base_onto[get_ontology_classname(desc)](ca)
      cai.label.append(ca)

def define_properties():
    with base_onto: # T-Box Declaration
        class hasObservation(ObjectProperty):
            pass
        class hasQuality(ObjectProperty):
            pass
        class observationOf(ObjectProperty, FunctionalProperty):
            inverse_property = hasObservation
        class hasUpperValue(DataProperty, FunctionalProperty): # Functional Property allows to assign only one value to Property)
            range = [float]
        class hasNominalValue(DataProperty, FunctionalProperty):
            range = [float]
        class hasLowerValue(DataProperty, FunctionalProperty):
            range = [float]
        class hasObservedValue(DataProperty, FunctionalProperty):
            range = [float]
        class hasFailureCause(ObjectProperty):
            pass
        class observesSpecification(ObjectProperty, FunctionalProperty):
            pass

def add_specs():
        df = pd.read_csv(f"{input_path}/specs_data.csv")
        # Get the first and second columns
        col1 = df.columns[1] # Specification Name
        col2 = df.columns[2] # Specification Values
        # Lowercase the values in column 1
        df[col1] = df[col1].str.lower()
        # Create dictionary: key = value from first column, value = value from second column
        quals_dict = {row[col1]: row[col2] for index, row in df[[col1, col2]].iterrows()}
        quals = {}
        for f in semicon_quality_concepts:
            assert f.lower() in quals_dict, f"{f} not found in specs"
            quals[f] = get_spec_values(quals_dict.get(f.lower()))
        with open(f"{output_path}/specs.json", "w") as f:
            json.dump(quals, f , indent=2)
        with product1_onto:
            i = 1
            for si in quals:
                base_onto_class = base_onto[get_ontology_classname(si)]
                onto_ins = base_onto_class(f"S{i}")
                onto_ins.label = [f"S{i}"]
                for value_type, value in quals[si].items():
                    if value_type == "NV":
                       onto_ins.hasNominalValue = value
                    elif value_type == "LL":
                       onto_ins.hasLowerValue = value
                    elif value_type == "UL":
                       onto_ins.hasUpperValue = value
                i+=1
            save_ontology()

def add_products():
    df = pd.read_csv(f"{input_path}/synthetic_data_factory.csv")
    # Strip spaces from column names
    df.columns = df.columns.str.strip() # Check specs in Synthetic Data files
    products_in_ontology = 1000
    with product1_onto: # A-box instantiation
        j = 1
        for entry in semicon_quality_concepts:
            assert entry.lower() in df.columns, f"Column '{entry}' is missing in Synthetic data!" # check whether the 'spec' exists in synthetic data file 
            qual_obs_classname = base_onto[get_ontology_classname(f"{entry} Obs")] # get reference to observed quality class
            product_class = base_onto[get_ontology_classname("Pcb Motherboard")] # get reference to material product class
            values = df[entry.lower()].tolist() # get all observed values corresponding to a 'spec'
            values = values[0:products_in_ontology] # limiting to first 20 observed values
            qual_ins = product1_onto[f"S{j}"] # Get reference to the 'Quality' Individual
            for i, v in enumerate(values): # create the datastructure (i,v) list
                onto_ins = product_class(f"PCB{i+1}") # start creating Product1 individuals
                onto_ins.label = [f"PCB{i+1}"] # assign a label
                onto_ins.hasQuality.append(qual_ins) # connect the 'Product1' individual with 'Quality' individual using 'IOF:hasQuality' which is not a functional property (hence using append)
                qual_observ_ins = qual_obs_classname(  # instantiating observed value individuals for Product1
                    f"Obs_{get_ontology_classname(entry)}_PCB{i+1}"
                    )
                qual_observ_ins.hasObservedValue = float(v) # assign hasobserved value to individual
                qual_observ_ins.observationOf = onto_ins # connect the observed value individual to the Product1 individual
                qual_observ_ins.observesSpecification = qual_ins # observed value individual describes the quality individual
            j += 1
        save_ontology() 
        #log the number of individuals
        print(f"{len(values)} product individuals imported to the ontology")
    return {"message": "products added"}

def add_and_run_rules():
    with product1_onto:
        rules = {
            "Stencil thickness too high": [
                """
                    StencilThicknessTooHigh(?r),
                    StencilThicknessObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val), hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?pcb, ?r)
                """
            ],
            "Excess squeegee pressure": [
                """
                    ExcessSqueegeePressure(?r),
                    SqueegeePressureObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?pcb, ?r)
                """
            ],
            "Insufficient squeegee pressure": [
                """
                    InsufficientSqueegeePressure(?r),
                    SqueegeePressureObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasLowerValue(?spec, ?lower),
                    lessThan(?val, ?lower) -> hasFailureCause(?pcb, ?r)
                """
            ],
            "Excess squeegee speed": [
                 """
                    ExcessSqueegeeSpeed(?r),
                    SqueegeeSpeedObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?pcb, ?r)
                """
            ],
            "Squeegee angle out of spec": [
                """
                    SqueegeeAngleOutOfSpec(?r),
                    SqueegeeAngleObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?pcb, ?r)
                """,
                 """
                    SqueegeeAngleOutOfSpec(?r),
                    SqueegeeAngleObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasLowerValue(?spec, ?lower),
                    lessThan(?val, ?lower) -> hasFailureCause(?pcb, ?r)
                """
            ],
            "Residual paste left on stencil edge": [
                 """
                    ResidualPasteLeftOnStencilEdge(?r),
                    ResidualPasteAllowedObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?pcb, ?r)
                """
            ],
            "Oversized stencil aperture or excessive overprint":[
                """
                    OversizedStencilApertureOrExcessiveOverprint(?r),
                    PasteVolumePerApertureObs(?obs),
                    observationOf(?obs, ?pcb), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?pcb, ?r)
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

    args = parser.parse_args()

    if args.init:
        initiate_ontology(create_new=False)
    elif args.init_new:
        initiate_ontology(create_new=True)
    if args.add_specs:
        add_specs()
    if args.add_products:
        add_products()
    if args.run_rules:
        add_and_run_rules()
    if args.export:
        export_ontology_to_graphdb(path)
    if args.report:
        create_reports()
    if args.clear:
        clear_graphdb_default_graph()
