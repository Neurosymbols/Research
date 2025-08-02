# CONFIDENTIAL 
# Copyright Abakai

import argparse
import os
import types
import json
import pandas as pd
import re
import requests

from owlready2 import *
from decimal import Decimal, getcontext
from pathlib import Path
from SPARQLWrapper import SPARQLWrapper, JSON


path = "./data/ontologies"
input_path = "./data/input"
output_path = "./data/output"

GDB_URL = "http://localhost:7200"
REPO = "demo-semicon"
sparql = SPARQLWrapper(f"{GDB_URL}/repositories/{REPO}")

#set the path where system generated ontologies will be saved
onto_path.append(path)

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

# Create list of SemicON base classes
semicon_base_classes = [
'Corrective Action',
'Defect',
'Failure Cause'
]

semicon_quality_concepts = [
'Stencil Thickness',
'Residual Paste Allowed',
'Paste volume per aperture',
'Squeegee pressure',
'Squeegee speed',
'Squeegee angle',
]

semicon_product_class = [
   'PCB Motherboard'
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

import_iof = False

def perform_sparql_query(query):
    sparql.setReturnFormat(JSON)
    sparql.setQuery(query)
    results = sparql.query().convert()
    return results

def clear_graphdb_default_graph():
    url = f"{GDB_URL}/repositories/{REPO}/statements"
    r = requests.delete(url)
    if r.status_code == 204:
        print("Default graph cleared successfully.")
    else:
        print(f"Error clearing default graph: {r.status_code} {r.text}")

def export_ontology_to_graphdb():
    base_onto_path = f"{path}/semicon-base.owl"
    product1_path = f"{path}/semicon-product1.owl"
    # Upload to repository
    headers = {
        "Content-Type": "application/rdf+xml"
    }
    with open(base_onto_path, "rb") as f:
        r = requests.post(
            f"{GDB_URL}/repositories/{REPO}/statements",
            headers=headers,
            data=f
        )
    with open(product1_path, "rb") as f:
        r = requests.post(
            f"{GDB_URL}/repositories/{REPO}/statements",
            headers=headers,
            data=f
        )
    if r.status_code == 204:
        print("OWL file uploaded successfully.")
    else:
        print(f"Error uploading: {r.status_code} {r.text}")

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
    #report 1
    rows = {}
    for row in results["results"]["bindings"]:
        product_label = row["productLabel"]["value"]
        if product_label not in rows:
           rows[product_label] = {"failure_causes": []}
        rows[product_label]['failure_causes'].append(row["failure_cause"]["value"])
    rows = dict(sorted(rows.items(), key=lambda x: int(x[0][3:])))
    report_1 = []
    for p, d in rows.items():
       s = 0
       for fc, desc in failure_cause_concepts.items():
        row = {}
        if s == 0:
            row['Product'] = p
            s = 1
        else:
           row['Product'] = ""
        row['Failure Cause'] = desc
        if fc in d['failure_causes']:
           row['Variable'] = 1
        else:
           row['Variable'] = 0
        report_1.append(row)
    pd.DataFrame(report_1).to_csv(f"{output_path}/rule_firing_report.csv", index=False)

def create_classname_syntax(classname):
   return "".join([word.capitalize() for word in classname.split(" ")])

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

def extract_floats(s):
    # Match optional sign, digits, optional decimal part
    return [float(num) for num in re.findall(r'[-+]?\d*\.\d+|[-+]?\d+', s)]

def sum_nos(arr):
    # Convert to strings to count decimal places
    str_values = [str(f) for f in arr]
    max_decimals = max(len(s.split('.')[1]) if '.' in s else 0 for s in str_values)

    # Set precision context
    getcontext().prec = max_decimals + 5  # extra buffer to avoid rounding errors

    # Convert to Decimal and sum
    total = sum(Decimal(str(f)) for f in arr)

    # Format with max decimal places
    return float(format(total, f'.{max_decimals}f'))

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
  with base_onto:
    for classname in semicon_base_classes:
      classname = "".join([word.capitalize() for word in classname.split(" ")])
      base_class = types.new_class(classname, (Thing,))
      base_class.label.append(classname)
    for classname in semicon_quality_concepts:
      classname = "".join([word.capitalize() for word in classname.split(" ")])
      if import_iof:
        quality_class = bfo.search_one(iri="*BFO_0000019")
        quality_class = types.new_class(classname, (quality_class,))
      else:
        quality_class = types.new_class(classname, (Thing,))
      quality_class.label.append(classname)
    for classname in semicon_quality_concepts:
      classname = "".join([word.capitalize() for word in classname.split(" ")])
      if import_iof:
        measurement_ice_class = iof.search_one(iri="*MeasurementInformationContentEntity")
        quality_obs_class = types.new_class(f"{classname}Obs", (measurement_ice_class,))
      else:
        quality_obs_class = types.new_class(f"{classname}Obs", (Thing,))
      quality_obs_class.label.append(f"{classname}Obs")
    for classname in semicon_defect_concepts:
      classname = "".join([word.capitalize() for word in classname.split(" ")])
      defect_class = types.new_class(classname, (base_onto.Defect,))
      defect_class.label.append(classname)
    for fc, desc in failure_cause_concepts.items():
      fc_classname = "".join([word.capitalize() for word in desc.split(" ")])
      fc_class = types.new_class(fc_classname, (base_onto.FailureCause,))
      fc_class.label.append(desc)
    for ca, desc in semicon_corrective_action_concepts.items():
      ca_classname = "".join([word.capitalize() for word in desc.split(" ")])
      ca_class = types.new_class(ca_classname, (base_onto.CorrectiveAction,))
      ca_class.label.append(desc)
    for classname in semicon_product_class:
       classname = "".join([word.capitalize() for word in classname.split(" ")])
       if import_iof:
        material_product_class = iof.search_one(iri="*MaterialProduct")
        product_class = types.new_class(f"{classname}", (material_product_class,))
       else:
        product_class = types.new_class(f"{classname}", (Thing,))
       product_class.label.append(classname)

def add_base_individuals():
  global failure_cause_concepts, semicon_corrective_action_concepts
  #add base individuals
  with product1_onto: # A-Box Declaration
    for fc, desc in failure_cause_concepts.items():
      #add failure cause individual
      fc_classname = "".join([word.capitalize() for word in desc.split(" ")])
      fci = base_onto[fc_classname](fc)
      fci.label.append(fc)
    for ca, desc in semicon_corrective_action_concepts.items():
      #add corrective action individual
      ca_classname = "".join([word.capitalize() for word in desc.split(" ")])
      cai = base_onto[ca_classname](ca)
      cai.label.append(ca)

def define_properties():
        with base_onto: # T-Box Declaration
            semicon_product_classes = [base_onto[create_classname_syntax(c)] for c in semicon_product_class]
            semicon_quality_classes = [base_onto[create_classname_syntax(c)] for c in semicon_quality_concepts]
            semicon_quality_obs_classes = [base_onto[f"{create_classname_syntax(c)}Obs"] for c in semicon_quality_concepts]
            semicon_failure_cause_classes = [base_onto[create_classname_syntax(v)] for c,v in failure_cause_concepts.items()]
            semicon_defect_classes = [base_onto[create_classname_syntax(d)] for d in semicon_defect_concepts]
            semicon_ca_classes = [base_onto[create_classname_syntax(v)] for ca, v in semicon_corrective_action_concepts.items()]
            
            #------------------------------ Object Properties ----------------------------------#
            class hasSpecification(ObjectProperty):
               pass
                # domain = semicon_product_classes
                # range = semicon_quality_classes
            # class hasObservation(ObjectProperty):
            #     domain = semicon_product_classes
            #     range = semicon_quality_obs_classes
            class observationOf(ObjectProperty, FunctionalProperty):
               pass
            #    domain = semicon_quality_obs_classes
            #    range = semicon_product_classes
            class observesSpecification(ObjectProperty, FunctionalProperty):
               pass
            #    domain = semicon_quality_obs_classes
            #    range = semicon_quality_classes
            class hasFailureCause(ObjectProperty):
               pass
                # domain = semicon_product_classes
                # range = semicon_failure_cause_classes
            class hasDefect(ObjectProperty):
               pass
            #    domain = semicon_product_classes
            #    range = semicon_defect_classes
            class hasCorrectiveAction(ObjectProperty):
               pass
            #    domain = semicon_failure_cause_classes
            #    range = semicon_ca_classes
            #------------------------------ Data Properties ----------------------------------#
            class hasUpperValue(DataProperty, FunctionalProperty): # Functional Property allows to assign only one value to Property)
               pass
                # domain = semicon_quality_classes
            class hasNominalValue(DataProperty, FunctionalProperty):
               pass
                # domain = semicon_quality_classes
            class hasLowerValue(DataProperty, FunctionalProperty):
               pass
                # domain = semicon_quality_classes
            class hasObservedValue(DataProperty, FunctionalProperty):
               pass
                # domain = semicon_quality_obs_classes
            class hasUnit(DataProperty, FunctionalProperty):
                pass
            class hasSeverity(DataProperty, FunctionalProperty):
                # domain = semicon_failure_cause_classes
                range = [int]
            class hasWeight(DataProperty, FunctionalProperty):
                # domain = semicon_failure_cause_classes
                range = [float]
            class hasRBIScore(DataProperty, FunctionalProperty):
            #    domain = semicon_product_classes
               range = [float]

def add_specs():
        df = pd.read_csv(f"{input_path}/specs_data.csv")
        # Get the first and second columns
        col1 = df.columns[1] # Specification Name
        col2 = df.columns[2] # Specification Values
        # Lowercase the values in column 1
        df[col1] = df[col1].str.lower()
        # Create dictionary: key = value from first column, value = value from second column
        quals_dict = dict(zip(df[col1], df[col2]))
        quals = {}
        for f in semicon_quality_concepts:
            assert f.lower() in quals_dict, f"{f} not found in specs"
            quals[f] = get_spec_values(quals_dict.get(f.lower()))
        with open(f"{output_path}/specs.json", "w") as f:
            json.dump(quals, f , indent=2)
        with product1_onto:
            i = 1
            for si in quals:
                classname = "".join([word.capitalize() for word in si.split(" ")])
                base_onto_class = base_onto[classname]
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
    with product1_onto: # A-box instantiation
        j = 1
        for entry in semicon_quality_concepts: 
            assert entry.lower() in df.columns, f"Column '{entry}' is missing in Synthetic data!" # check whether the 'spec' exists in synthetic data file
            values = df[entry.lower()].tolist()[0:20] # get all observed values corresponding to a 'spec'. Limiting to first 20 observed values

            PCBMotherboard = base_onto['PcbMotherboard'] # get reference to pcb motherboard class
            qual_ins = product1_onto[f"S{j}"] # Get reference to the 'Quality' Individual
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
                # onto_ins.hasObservation.append(qual_observ_ins) # connect the observed value individual to the Product1 individual
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
        export_ontology_to_graphdb()
    if args.report:
        create_reports()
    if args.clear:
        clear_graphdb_default_graph()
