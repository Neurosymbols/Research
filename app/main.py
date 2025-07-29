# CONFIDENTIAL 
# Copyright Abakai

from owlready2 import *
import os
import types
import json
import pandas as pd
import re
from decimal import Decimal, getcontext

path = "./data/ontologies"
input_path = "./data/input"
output_path = "./data/output"

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
    iof = get_ontology(IOF_CORE_IRI).load()
    bfo = get_ontology(BFO_IRI).load()
    if not create_new:
        # When ontologies exist in ontologies folder
        base_onto = base_onto.load()
        product1_onto = product1_onto.load()
        #idempotently import ontologies
        base_onto.imported_ontologies.append(iof)
        product1_onto.imported_ontologies.append(base_onto)
    else:
        # When ontologies do not exist in ontologies folder, create them for the first time
        add_base_classes() # T-Box
        add_base_individuals() # A-Box
        define_properties() # T-Box
        #idempotently import ontologies
        base_onto.imported_ontologies.append(iof) # SemicON Base Onto imports IOF
        product1_onto.imported_ontologies.append(base_onto) # Product1 Onto imports the SemicON Base Onto
        save_ontology()

def save_ontology():
    global base_onto, product1_onto, path
    print(f"Total individuals inside SemicON Base: {len(list(base_onto.individuals()))}")
    print(f"Total individuals inside SemicON Product1: {len(list(product1_onto.individuals()))}")
    base_onto.save(file=os.path.join(path, "semicon-base.owl"), format = "rdfxml")
    product1_onto.save(file=os.path.join(path, "semicon-product1.owl"), format = "rdfxml")

def add_base_classes():
  global base_onto, iof, bfo, product1_onto, failure_cause_concepts, semicon_defect_concepts, semicon_corrective_action_concepts, failure_cause_concepts, semicon_quality_concepts, semicon_base_classes
  #add base classes
  with base_onto: # T-Box Declaration
    for classname in semicon_base_classes:
      classname = "".join([word.capitalize() for word in classname.split(" ")]) # CamelCase compliance
      base_class = types.new_class(classname, (Thing,))
      base_class.label.append(classname)
    for classname in semicon_quality_concepts:
      classname = "".join([word.capitalize() for word in classname.split(" ")])
      quality_class = bfo.search_one(iri="*BFO_0000019") #BFO 'Quality' Class lookup
      quality_class = types.new_class(classname, (quality_class,))
      quality_class.label.append(classname)
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
        global iof, base_onto, bfo
        with base_onto: # T-Box Declaration
            MaterialProduct = iof.search_one(iri="*MaterialProduct")
            MeasurementICE  = iof.search_one(iri="*MeasurementInformationContentEntity")
            Quality = bfo.search_one(iri="*BFO_0000019")
            class hasObservation(ObjectProperty):
                domain = [MaterialProduct]
                range = [MeasurementICE]
            class observationOf(ObjectProperty):
                inverse_property = hasObservation
            class hasUpperValue(DataProperty, FunctionalProperty): # Functional Property allows to assign only one value to Property)
                domain = [Quality]
            class hasNominalValue(DataProperty, FunctionalProperty):
                domain = [Quality]
            class hasLowerValue(DataProperty, FunctionalProperty):
                domain = [Quality]
            class hasObservedValue(DataProperty, FunctionalProperty):
                domain = [Quality]
            class hasUnit(DataProperty, FunctionalProperty):
                pass
            class hasSeverity(DataProperty, FunctionalProperty):
                domain = [base_onto.FailureCause]
                range = [int]
            class hasWeight(DataProperty, FunctionalProperty):
                domain = [base_onto.FailureCause]
                range = [float]
            class hasFailureCause(ObjectProperty):
                domain = [MaterialProduct]
                range = [base_onto.FailureCause]
            class hasDefect(ObjectProperty):
               domain = [MaterialProduct]
               range = [base_onto.Defect]
            class hasCorrectiveAction(ObjectProperty):
               domain = [base_onto.FailureCause]
               range = [base_onto.CorrectiveAction]
            class hasRBIScore(DataProperty, FunctionalProperty):
               domain = [MaterialProduct]
               range = [float]
            class isCauseOf(ObjectProperty):
               domain = [base_onto.FailureCause]
               range = [base_onto.Defect]
            class isCausedBy(ObjectProperty):
               inverse_property = isCauseOf

def add_specs():
        global input_path, semicon_quality_concepts, output_path, product1_onto, base_onto
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
    global product1_onto, iof
    df = pd.read_csv(f"{input_path}/synthetic_data_factory.csv")
    # Strip spaces from column names
    df.columns = df.columns.str.strip() # Check specs in Synthetic Data files
    with product1_onto: # A-box instantiation
        j = 1
        for entry in semicon_quality_concepts: 
            qual_classname = "".join([word.capitalize() for word in entry.split(" ")])
            assert entry.lower() in df.columns, f"Column '{entry}' is missing in Synthetic data!" # check whether the 'spec' exists in synthetic data file
            values = df[entry.lower()].tolist() # get all observed values corresponding to a 'spec'
            values = values[0:20] # limiting to first 20 observed values
            MaterialProduct = iof.search_one(iri="*MaterialProduct") # get reference to material product class
            # print(MaterialProduct)
            MeasurementICE  = iof.search_one(iri="*MeasurementInformationContentEntity") # get reference to MeasurementICE product class
            # print(MeasurementICE)
            qual_ins = product1_onto[f"S{j}"] # Get reference to the 'Quality' Individual
            # print(qual_ins)
            for i, v in enumerate(values): # create the datastructure (i,v) list
                onto_ins = MaterialProduct(f"PCB{i+1}") # start creating Product1 individuals
                onto_ins.label = [f"PCB{i+1}"] # assign a label
                onto_ins.hasQuality.append(qual_ins) # connect the 'Product1' individual with 'Quality' individual using 'IOF:hasQuality' which is not a functional property (hence using append)
                qual_observ_ins = MeasurementICE(  # instantiating observed value individuals for Product1
                    f"Obs_{qual_classname}_PCB{i+1}"
                    )
                qual_observ_ins.describes.append(qual_ins) # observed value individual describes the quality individual
                qual_observ_ins.hasObservedValue = float(v) # assign hasobserved value to individual
                onto_ins.hasObservation.append(qual_observ_ins) # connect the observed value individual to the Product1 individual
            j += 1
        save_ontology()
        #log the number of individuals
        print(f"{len(values)} product individuals imported to the ontology")

    return {"message": "products added"}
initiate_ontology(create_new=False)
add_specs()
add_products()
