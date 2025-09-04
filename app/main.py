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
#TODO: Introduce IOF and BFO stubs(BFO:Quality, IOF:MeasurementICE, IOF:MaterialProduct), MIREOT
semicon_base_classes = [
'Corrective Action',
'Defect',
'Failure Cause',
'PCB',
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

monitor_defect = "Solder Bridging"

failure_cause_concepts = {
  "FC1": {
    "desc": "Oversized stencil aperture or excessive overprint",
    "severity": 9,
    "weight": 0.32
  },
  "FC2": {
    "desc": "Excess squeegee pressure",
    "severity": 4,
    "weight": 0.07
  },
  "FC3": {
    "desc": "Stencil thickness too high",
    "severity": 8,
    "weight": 0.25
  },
  "FC4": {
    "desc": "Insufficient squeegee pressure",
    "severity": 3,
    "weight": 0.05
  },
  "FC5": {
    "desc": "Excess squeegee speed",
    "severity": 3,
    "weight": 0.04
  },
  "FC6": {
    "desc": "Squeegee angle out of spec",
    "severity": 4,
    "weight": 0.06
  },
  "FC7": {
    "desc": "Residual paste left on stencil edge",
    "severity": 4,
    "weight": 0.06
  }
}

semicon_corrective_action_concepts = {
    'CAFC1':{
        "desc": "Adjust print parameters to avoid overprinting or Redesign stencil apertures to appropriate size",
        "failure_cause": "FC1"
    },
    'CAFC2':{
        "desc": "Optimize squeegee pressure settings",
        "failure_cause": "FC2"
    },
    'CAFC3':{
        "desc": "Swap the stencil to the specified thickness for this product",
        "failure_cause": "FC3"
    },
    'CAFC4':{
        "desc": "Optimize squeegee pressure settings",
        "failure_cause": "FC4"
    },
    'CAFC5':{
        "desc": "Adjust squeegee speed to recommended range",
        "failure_cause": "FC5"
    },
    'CAFC6':{
        "desc": "Set squeegee at proper angle (e.g., 45°)",
        "failure_cause": "FC6"
    },
    'CAFC7':{
        "desc": "Increase stencil cleaning frequency",
        "failure_cause": "FC7"
    }
}

def create_reports():
    results = perform_sparql_query(
        query = '''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?defectLabel (COALESCE(?desc, "No Failure Cause") AS ?failure_cause)
            WHERE {
                ?defect a base:SolderBridging ;
                        rdfs:label ?defectLabel;
                        

                OPTIONAL {
                    ?defect base:hasFailureCause ?failurecause .
                    ?failurecause rdfs:label ?desc .
                }
            }
            ORDER BY ?defect
        '''
    )
    # 1) Group all failure-cause IDs by product
    #    Example: grouped["PCB1"] = set(["FC1", "FC3", ...])
    grouped = defaultdict(set)
    for row in results["results"]["bindings"]:
        product = row["defectLabel"]["value"]
        fc_id   = row["failure_cause"]["value"]
        grouped[product].add(fc_id)
    
    # 2) Sort products by the number that appears after the first 3 characters.
    #    Original code did: int(product[3:])
    #    This helper keeps it robust if a name doesn’t match that pattern.
    def product_sort_key(name: str) -> int:
        try:
            product_label = name.split("_")[1]
            return int(product_label[3:])
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

        for fc_id, fc_data in failure_cause_concepts.items():
            rows_for_csv.append({
                "Product": product if first_line_for_product else "",
                "Failure Cause": fc_data['desc'],                  # human-friendly text
                "Variable": 1 if f"{fc_id} - {fc_data['desc']}" in seen_fc_ids else 0  # 1 = fired, 0 = not fired
            })
            first_line_for_product = False
    
    pd.DataFrame(rows_for_csv).to_csv(f"{output_path}/rule_firing_report.csv", index=False)


# Initiate the ontology (set create_new = true if ontologies need to be created from scratch everytime)
def initiate_ontology(create_new):
    global base_onto, product1_onto
    #initiating empty ontology objects
    base_onto = get_ontology(BASE_ONTO_IRI)
    product1_onto = get_ontology(PRODUCT_ONTO_IRI)
    if not create_new:
        # When ontologies exist in ontologies folder
        base_onto = base_onto.load()
        product1_onto = product1_onto.load()
    else:
        # When ontologies do not exist in ontologies folder, create them for the first time
        add_base_classes() # T-Box
        define_properties() # T-Box
        add_base_individuals() # A-Box
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
    for fc, data in failure_cause_concepts.items():
      fc_class = types.new_class(get_ontology_classname(f"class{fc}"), (base_onto.FailureCause,))
      fc_class.label.append(data['desc'])
    for ca, data in semicon_corrective_action_concepts.items():
      ca_class = types.new_class(get_ontology_classname(f"class{ca}"), (base_onto.CorrectiveAction,))
      ca_class.label.append(data['desc'])

def add_base_individuals():
  #add base individuals
  with product1_onto: # A-Box Declaration
    failure_cause_ca_mapping = {}
    for ca, data in semicon_corrective_action_concepts.items():
      #add corrective action individual
      cai = base_onto[get_ontology_classname(f"class{ca}")](ca)
      cai.label.append(f"{ca} - {data['desc']}")
      if data['failure_cause'] not in failure_cause_ca_mapping:
          failure_cause_ca_mapping[data['failure_cause']] = []
      failure_cause_ca_mapping[data['failure_cause']].append(ca)
    for fc, data in failure_cause_concepts.items():
      #add failure cause individual
      fci = base_onto[get_ontology_classname(f"class{fc}")](fc)
      fci.label.append(f"{fc} - {data['desc']}")
      #assign corrective action to failure cause
      cas_for_fc = failure_cause_ca_mapping[fc] 
      for ca in cas_for_fc:
        fci.hasCorrectiveAction.append(product1_onto[ca])
      fci.hasWeight = data['weight']
      fci.hasSeverity = data['severity']

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
        class hasCorrectiveAction(ObjectProperty):
            pass
        class hasWeight(DataProperty, FunctionalProperty):
            range = [float]
        class hasSeverity(DataProperty, FunctionalProperty):
            range = [int]
        class monitorsDefect(ObjectProperty, FunctionalProperty):
            pass

def add_specs():
    quals = json.load(open(f"{input_path}/specs.json"))
    with product1_onto: # A-box instantiation
        i = 1
        #quals contains the 6 quality names(specifications)
        for si, data in quals.items():
            #si = Stencil Thickness
            base_onto_class = base_onto[get_ontology_classname(si)] #returns class: StencilThickness
            onto_ins = base_onto_class(f"S{i}") #instantiate StencilThickness object with label S{i}
            onto_ins.label = [f"S{i} - {si}"]
            for value_type, value in data.items():
                if value_type == "NV":
                    onto_ins.hasNominalValue = value
                elif value_type == "LL":
                    onto_ins.hasLowerValue = value
                elif value_type == "UL":
                    onto_ins.hasUpperValue = value
            i+=1
        save_ontology()

def create_defect_individuals(product_label:str, quality_obs_ind):
    with product1_onto:
        for d in semicon_defect_concepts:
            if d.lower() == monitor_defect.lower():
                defect_name = get_ontology_classname(d)
                defect_class = base_onto[defect_name]
                defect_ind  = defect_class(f"{defect_name}_{product_label}")
                defect_ind.label.append(f"{defect_name}_{product_label}")
                quality_obs_ind.monitorsDefect = defect_ind

def add_products():
    df = pd.read_csv(f"{input_path}/synthetic_data_factory.csv")
    # Strip spaces from column names
    df.columns = df.columns.str.strip() # Check specs in Synthetic Data files
    products_in_ontology = 1000
    with product1_onto: # A-box instantiation
        j = 1
        #looping over 6 specification names
        for entry in semicon_quality_concepts:
            #entry:= Stencil Thickness
            assert entry.lower() in df.columns, f"Column '{entry}' is missing in Synthetic data!" # check whether the 'spec' exists in synthetic data file 
            #base_onto[StencilThicknessObs] - reference to StencilThicknessObs class
            qual_obs_classname = base_onto[get_ontology_classname(f"{entry} Obs")] # get reference to observed quality class
            #base_onto[PCB] - reference to PCB class
            product_class = base_onto[get_ontology_classname("Pcb")] # get reference to material product class
            #df[stencil thickness].tolist()
            values = df[entry.lower()].tolist() # get all observed values corresponding to a 'spec'
            #get first 1000 observed values for stencil thickness
            values = values[0:products_in_ontology] # limiting to first n observed values
            #get reference Stencil Thickness quality individual: product1_onto['S1']
            qual_ins = product1_onto[f"S{j}"] # Get reference to the 'Quality' Individual
            for i, v in enumerate(values): # create the datastructure (i,v) list
                pcb_individual = product_class(f"PCB{i+1}") # start creating Product1 individuals
                pcb_individual.label = [f"PCB{i+1}"] # assign a label
                pcb_individual.hasQuality.append(qual_ins) # connect the 'Product1' individual with 'Quality' individual using 'IOF:hasQuality' which is not a functional property (hence using append)
                qual_observ_ins = qual_obs_classname(  # instantiating observed value individuals for Product1
                    f"{get_ontology_classname(entry)}_PCB{i+1}_Obs"
                    )
                create_defect_individuals(
                    f"PCB{i+1}",
                    qual_observ_ins
                )
                qual_observ_ins.hasObservedValue = float(v) # assign hasobserved value to individual
                qual_observ_ins.observationOf = pcb_individual # connect the observed value individual to the Product1 individual
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
                    Classfc3(?r),
                    StencilThicknessObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val), hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r)
                """
            ],
            "Excess squeegee pressure": [
                """
                    Classfc2(?r),
                    SqueegeePressureObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r)
                """
            ],
            "Insufficient squeegee pressure": [
                """
                    Classfc4(?r),
                    SqueegeePressureObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasLowerValue(?spec, ?lower),
                    lessThan(?val, ?lower) -> hasFailureCause(?d, ?r)
                """
            ],
            "Excess squeegee speed": [
                 """
                    Classfc5(?r),
                    SqueegeeSpeedObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r)
                """
            ],
            "Squeegee angle out of spec": [
                """
                    Classfc6(?r),
                    SqueegeeAngleObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r)
                """,
                 """
                    Classfc6(?r),
                    SqueegeeAngleObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasLowerValue(?spec, ?lower),
                    lessThan(?val, ?lower) -> hasFailureCause(?d, ?r)
                """
            ],
            "Residual paste left on stencil edge": [
                 """
                    Classfc7(?r),
                    ResidualPasteAllowedObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r)
                """
            ],
            "Oversized stencil aperture or excessive overprint":[
                """
                    Classfc1(?r),
                    PasteVolumePerApertureObs(?obs),
                    monitorsDefect(?obs, ?d), observesSpecification(?obs, ?spec),
                    hasObservedValue(?obs, ?val),hasUpperValue(?spec, ?upper),
                    greaterThan(?val, ?upper) -> hasFailureCause(?d, ?r)
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
