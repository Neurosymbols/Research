import json
import pandas as pd
import yaml
from typing import Optional
from owlready2 import *
import owlready2.reasoning
# Patch the default -Xmx value
owlready2.reasoning.JAVA_MEMORY = "12288"
from app.services.utils import replace_iri, add_classes, add_individuals, create_classname_syntax, get_failure_cause_concepts, perform_sparql_update, perform_sparql_query

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

super_base_classes = [
    'Action Specification',
    'Specifically Dependent Continuant',
    'Material Product',
    'Quality',
    'Measurement Information Content Entity'
]
# Create list of SemicON base classes
semicon_material_artifacts = [
   'PCB'
]
semicon_action_specifications = [
    'Corrective Action'
]
semicon_sdcs = [
    'Defect',
    'Failure Cause'
]

semicon_fc_subtypes = [
    'RootCause'
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
    semicon_defect_concepts = list(base_classes.get("defects_and_failure_causes", {}).get("defect", []))
    semicon_quality_concepts = list(base_classes.get('semicon_quality_concepts').keys())
    semicon_corrective_action_concepts = base_classes.get('semicon_corrective_action_concepts', {})
    failure_cause_concepts = list(base_classes.get("defects_and_failure_causes", {}).get("failure_cause", []))
    add_classes(
        super_base_classes,
        Thing,
        base_onto
    )
    add_classes(
        semicon_action_specifications,
        iof.search_one(iri="*ActionSpecification") if import_iof else base_onto.search_one(iri="*ActionSpecification"),
        base_onto
    )
    add_classes(
        semicon_sdcs,
        bfo.search_one(iri="*BFO_0000020") if import_iof else base_onto.search_one(iri="*SpecificallyDependentContinuant"),
        base_onto
    )
    add_classes(
        semicon_material_artifacts,
        iof.search_one(iri="*MaterialProduct") if import_iof else base_onto.search_one(iri="*MaterialProduct"),
        base_onto
    )
    add_classes(
       semicon_quality_concepts,
       bfo.search_one(iri="*BFO_0000019") if import_iof else base_onto.search_one(iri="*Quality"),
       base_onto
    )
    add_classes(
       [f"{s} obs" for s in semicon_quality_concepts],
       iof.search_one(iri="*MeasurementInformationContentEntity") if import_iof else base_onto.search_one(iri="*MeasurementInformationContentEntity"),
       base_onto
    )
    add_classes(
        semicon_defect_concepts,
        base_onto.Defect,
        base_onto
    )
    add_classes(
        [fc for fc in failure_cause_concepts],
        base_onto.FailureCause,
        base_onto
    )
    add_classes(
        [fc for fc in semicon_fc_subtypes],
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
                    if prop.get("transitive"):
                        bases.append(TransitiveProperty)
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

def add_specs_to_ontology(specs_dict, ontology_path):
    if product1_onto is not None:
        with product1_onto:
            for si in specs_dict:
                classname = create_classname_syntax(si)
                base_onto_class = base_onto[classname]
                onto_ins = base_onto_class(specs_dict[si]['id'])
                onto_ins.label = [specs_dict[si]['id']]
                for value_type, value in specs_dict[si].items():
                    if value_type == "NOM":
                        onto_ins.hasNominalValue = value
                    elif value_type == "LSL":
                        onto_ins.hasLowerValue = value
                    elif value_type == "USL":
                        onto_ins.hasUpperValue = value
            save_ontology(ontology_path)

def add_defect_individuals(
    product_individual,
    semicon_defect_concepts:list,
    observation_individual
):
   if product1_onto is not None:
    with product1_onto:
        for defect_name in semicon_defect_concepts:
            defect_classname = create_classname_syntax(defect_name)
            product_individual_label = product_individual.label[0]
            defect_individual = base_onto[defect_classname](f"{defect_classname}_{product_individual_label}")
            defect_individual.label.append(f"{defect_classname}_{product_individual_label}")
            defect_individual.flagCount = 0
            defect_individual.interactionBonus = 0
            observation_individual.monitorsDefect.append(defect_individual)
            product_individual.hasPotentialDefect.append(defect_individual)

def add_products_to_ontology(
    batch_size:int,
    synthetic_data_factory_file: str,
    defects_and_failure_causes: dict,
    semicon_quality_concepts: dict,
    ontology_path:str
):
    semicon_defect_concepts = list(defects_and_failure_causes.get("defect", []))
    df = pd.read_csv(synthetic_data_factory_file)
    # Strip spaces from column names
    df.columns = df.columns.str.strip() # Check specs in Synthetic Data files
    if product1_onto is not None:
        with product1_onto: # A-box instantiation
            for entry in semicon_quality_concepts:
                entry_class_syntax = create_classname_syntax(entry)
                if entry_class_syntax in df.columns:
                    values = df[entry_class_syntax].tolist()[0:batch_size] # get all observed values corresponding to a 'spec'. Limiting to first 20 observed values
                    #create defect individuals
                    PCB = base_onto['PCB'] # get reference to pcb class
                    qual_ins = product1_onto[semicon_quality_concepts[entry]['id']] # Get reference to the 'Quality' Individual
                    for i, v in enumerate(values): # create the datastructure (i,v) list
                        product_individual = PCB(f"PCB{i+1}") # start creating Product1 individuals
                        product_individual.label = [f"PCB{i+1}"] # assign a label
                        product_individual.hasSpecification.append(qual_ins) # connect the 'Product1' individual with 'Quality' individual using 'Semi:hasSpecification' which is not a functional property (hence using append)
                        observation_individual =  base_onto[f"{entry_class_syntax}Obs"](  # instantiating observed value individuals for Product1
                            f"{entry_class_syntax}_PCB{i+1}_Obs"
                            )
                        observation_individual.evaluatesAgainst = qual_ins # observed value individual describes the quality individual
                        observation_individual.hasObservedValue = float(v) # assign hasobserved value to individual
                        observation_individual.observationOf = product_individual
                        add_defect_individuals(
                            product_individual,
                            semicon_defect_concepts,
                            observation_individual,
                        )
            save_ontology(ontology_path)
            #log the number of individuals
            print(f"{len(values)} product individuals imported to the ontology")

    return {"message": "products added"}

def run_rules(rules, path):
    root_cause_query = '''
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT ?defectLabel ?ruleFired ?violatedSpec
        WHERE{
        ?defect a base:SolderBridging ;
                rdfs:label ?defectLabel .
        OPTIONAL {
                ?defect base:hasFailureCause ?fc .
                ?fc rdfs:label ?ruleFired .
            }
        }
    '''
    for rulename, rulelist in rules.items():
        for ri in rulelist:
            print(ri)
            #run rules
            t1 = time.time()
            perform_sparql_update(ri)
            t2 = time.time()
            print(f"{t2-t1}s taken to run the reasoner for {rulename}")
    results = perform_sparql_query(root_cause_query)
    result_rows = results['results']['bindings']
    root_cause_report = {}
    for row in result_rows:
        defectLabel = row['defectLabel']['value']
        if defectLabel not in root_cause_report:
            root_cause_report[defectLabel] = {"failure_causes": {}}
        failure_cause = row.get('ruleFired', {}).get('value', "")
        if failure_cause:
            if failure_cause not in root_cause_report[defectLabel]['failure_causes']:
                root_cause_report[defectLabel]['failure_causes'][failure_cause] = []
    with open(f"{path}/root_cause_report.json", "w") as f:
        json.dump(root_cause_report, f, indent=2)
    return {"message": "sparql construct ran successfully", "time_taken": f"{t2-t1}s"}