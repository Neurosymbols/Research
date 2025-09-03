import pandas as pd
import yaml
from typing import Optional
from owlready2 import *
from app.services.utils import replace_iri, add_classes, add_individuals, create_classname_syntax, get_failure_cause_concepts

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

# Create list of SemicON base classes
semicon_base_classes = [
    'Corrective Action',
    'Defect',
    'Failure Cause'
]
semicon_product_class = [
   'PCB Motherboard'
]

# Initiate the ontology (set create_new = true if ontologies need to be created from scratch everytime)
def initiate_ontology(
        create_new, 
        ontologies_path = None, 
        properties_path = None,
        base_classes = None
    ):
    global base_onto, product1_onto
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
        add_base_classes(base_classes) # T-Box
        define_properties(properties_path) # T-Box
        add_base_individuals(base_classes) # A-Box
        if import_iof:
            #idempotently import ontologies
            base_onto.imported_ontologies.append(iof) # SemicON Base Onto imports IOF
        product1_onto.imported_ontologies.append(base_onto) # Product1 Onto imports the SemicON Base Onto
        save_ontology(ontologies_path)

def save_ontology(path:str):
    print(f"Total individuals inside SemicON Base: {len(list(base_onto.individuals()))}")
    print(f"Total individuals inside SemicON Product1: {len(list(product1_onto.individuals()))}")
    base_onto.save(file=os.path.join(path, "semicon-base.owl"), format = "rdfxml")
    product1_onto.save(file=os.path.join(path, "semicon-product1.owl"), format = "rdfxml")
    if import_iof:
        replace_iri()

def add_base_classes(
    base_classes
):
    #add base classes
    #T-BOX declaration
    semicon_defect_concepts = list(base_classes.get('failure_causes_rules_mapping').keys())
    semicon_quality_concepts = list(base_classes.get('semicon_quality_concepts').keys())
    semicon_corrective_action_concepts = base_classes.get('semicon_corrective_action_concepts', {})
    failure_cause_concepts = get_failure_cause_concepts(base_classes.get('failure_causes_rules_mapping'))
    print(failure_cause_concepts)
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
        [fc for fc, desc in failure_cause_concepts.items()],
        base_onto.FailureCause,
        base_onto
    )
    add_classes(
        [desc for ca, desc in semicon_corrective_action_concepts.items()],
        base_onto.CorrectiveAction,
        base_onto
    )

def define_properties(input_path):
    with open(input_path) as f:
        config = yaml.safe_load(f)
        if base_onto is not None:
            with base_onto: # T-Box Declaration
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

def add_base_individuals(
    base_classes
):
  #add base individuals
  # A-Box Declaration
  #adding universal failure cause individuals with severity and weights
  semicon_corrective_action_concepts = base_classes.get('semicon_corrective_action_concepts', {})
  failure_causes_rules_mapping = base_classes.get('failure_causes_rules_mapping')
  if product1_onto is not None:
    with product1_onto:
        for defect, defect_info in failure_causes_rules_mapping.items():
            for fc_name, fc_data in defect_info.items():
                ind = base_onto[create_classname_syntax(fc_name)](fc_data['id'])
                ind.label.append(fc_data['id'])
                ind.hasSeverity = fc_data['severity']
                ind.hasWeight = fc_data['weight']
        add_individuals(
            semicon_corrective_action_concepts,
            product1_onto,
            base_onto
        )

def add_specs_to_ontology(specs_dict, ontology_path):
    if product1_onto is not None:
        with product1_onto:
            for si in specs_dict:
                classname = "".join([word.capitalize() for word in si.split(" ")])
                base_onto_class = base_onto[classname]
                onto_ins = base_onto_class(specs_dict[si]['id'])
                onto_ins.label = [specs_dict[si]['id']]
                for value_type, value in specs_dict[si].items():
                    if value_type == "NV":
                        onto_ins.hasNominalValue = value
                    elif value_type == "LL":
                        onto_ins.hasLowerValue = value
                    elif value_type == "UL":
                        onto_ins.hasUpperValue = value
            save_ontology(ontology_path)

def add_defect_individuals(batch_size:int, failure_causes_rules_mapping:dict):
   if product1_onto is not None:
    with product1_onto:
        for defect_name in failure_causes_rules_mapping:
            defect_classname = create_classname_syntax(defect_name)
            for i in range(batch_size):
                defect_individual = base_onto[defect_classname](f"{defect_classname}_PCB{i+1}")
                defect_individual.label.append(f"{defect_classname}_PCB{i+1}")

def add_products_to_ontology(
    batch_size:int,
    synthetic_data_factory_file: str,
    failure_causes_rules_mapping: dict,
    semicon_quality_concepts: dict,
    ontology_path:str
):
    semicon_defect_concepts = list(failure_causes_rules_mapping.keys())
    df = pd.read_csv(synthetic_data_factory_file)
    # Strip spaces from column names
    df.columns = df.columns.str.strip() # Check specs in Synthetic Data files
    # Normalize all column names to lowercase once
    lower_cols = [col.lower() for col in df.columns]
    if product1_onto is not None:
        with product1_onto: # A-box instantiation
            for entry in semicon_quality_concepts: 
                assert entry.lower() in lower_cols, f"Column '{entry}' is missing in Synthetic data!" # check whether the 'spec' exists in synthetic data file
                values = df[entry].tolist()[0:batch_size] # get all observed values corresponding to a 'spec'. Limiting to first 20 observed values
                #create defect individuals
                add_defect_individuals(batch_size, failure_causes_rules_mapping)
                PCBMotherboard = base_onto['PcbMotherboard'] # get reference to pcb motherboard class
                qual_ins = product1_onto[semicon_quality_concepts[entry]['id']] # Get reference to the 'Quality' Individual
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
                        qual_observ_ins.monitorsDefect.append(defect_ind)
                        defect_ind.flagCount = 0
                        defect_ind.interactionBonus = 0
                    # onto_ins.hasObservation.append(qual_observ_ins) # connect the observed value individual to the Product1 individual
            save_ontology(ontology_path)
            #log the number of individuals
            print(f"{len(values)} product individuals imported to the ontology")

    return {"message": "products added"}

def run_rules(rules, ontology_path):
    if product1_onto is not None:
        with product1_onto:
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
            save_ontology(ontology_path)
            return {"message": "pellet ran successfully", "time_taken": f"{t2-t1}s"}