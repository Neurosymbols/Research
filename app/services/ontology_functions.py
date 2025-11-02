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
BASE_ONTO_IRI = "https://neurosymbols.ai/ontology/causal-terminology.owl"
PRODUCT_ONTO_IRI = "https://neurosymbols.ai/data/causal-assertions.owl"
IOF_IRI = "https://spec.industrialontologies.org/ontology/core/Core/"
BFO_IRI = "http://purl.obolibrary.org/obo/"

base_path = "./app/data"
path = f"{base_path}/ontologies/epoch3-7"
input_path = f"{base_path}/input/epoch3-7"

# Initialize Variables to store ontology objects in memory
base_onto = None
product1_onto = None
iof = None
bfo = None
ro = None
prov = None

import_ontologies = True
prefix_onto_map = {
    "IOF": iof,
    "BFO": bfo,
    "RO": ro,
    "prov": prov
}

super_base_classes = [
    'Action Specification',
    'Specifically Dependent Continuant',
    'Material Product',
    'Quality',
    'Measurement Information Content Entity',
    'Requirement Specification',
    'Process Characteristic',
    'Manufacturing Process',
    'Activity'
]
# Create list of SemicON base classes
semicon_material_artifacts = [
   'PCB'
]
semicon_measurement_ices = [
    'ParameterObservation'
]
semicon_req_ices = [
    'ParameterSpecification'
]
semicon_quality = [
    'ParameterQuality'
]
semicon_process_characteristic = [
    'ParameterCharacteristic'
]
semicon_action_specifications = [
    'CorrectiveAction'
]
#TODO: add cause
semicon_sdcs = [
    'Defect',
    'FailureCause',
    'Effect'
]

semicon_activity = [
    'ConformanceAssessment'
]

semicon_fc_subtypes = [
    'RootCause'
]

# Initiate the ontology (set create_new = true if ontologies need to be created from scratch everytime)
def initiate_ontology(
        create_new, 
        ontologies_path = None, 
        properties_path = None,
        base_classes = None,
        axioms_dict = None,
        defintions_dict = None
    ):
    global base_onto, product1_onto, iof, ro, bfo, prov, prefix_onto_map
    base_onto = get_ontology(BASE_ONTO_IRI)
    product1_onto = get_ontology(PRODUCT_ONTO_IRI)
    if not create_new:
        # When ontologies exist in ontologies folder
        base_onto = base_onto.load()
        product1_onto = product1_onto.load()
    else:
        # When ontologies do not exist in ontologies folder, create them for the first time
        if import_ontologies:
            iof = get_ontology(f"{path}/iof-core.rdf").load(only_local=True)
            bfo = get_ontology(f"{path}/bfo.owl").load(only_local=True)
            ro = get_ontology(f"{path}/ro-causal-properties.owl").load(only_local=True)
            prov = get_ontology(f"{path}/bfo-prov.owl").load(only_local=True)
        prefix_onto_map = {
            "IOF": iof,
            "BFO": bfo,
            "RO": ro,
            "prov": prov
        }
        add_base_classes(base_classes) # T-Box
        define_properties(properties_path) # T-Box
        add_axioms_to_ontology(axioms_dict) # T-Box
        add_base_class_types(base_classes) # T-Box
        add_defintions_and_examples(defintions_dict) # T-Box
        add_ishikawa_causal_graph() #T-Box
        if import_ontologies:
            #idempotently import ontologies
            base_onto.imported_ontologies.append(prov)
            base_onto.imported_ontologies.append(iof) # SemicON Base Onto imports IOF
            base_onto.imported_ontologies.append(ro)
        product1_onto.imported_ontologies.append(base_onto) # Product1 Onto imports the SemicON Base Onto
        save_ontology(ontologies_path)

def save_ontology(path:str):
    print(f"Total individuals inside SemicON Base: {len(list(base_onto.individuals()))}")
    print(f"Total individuals inside SemicON Product1: {len(list(product1_onto.individuals()))}")
    base_onto.save(file=os.path.join(path, "causal-terminology.owl"), format = "rdfxml")
    product1_onto.save(file=os.path.join(path, "causal-assertions.owl"), format = "rdfxml")

def add_base_classes(
    base_classes
):
    #add base classes
    #T-BOX declaration
    manufacturing_process_concepts = base_classes.get("manufacturing_process_concepts", [])
    if not import_ontologies:
        add_classes(
            super_base_classes,
            Thing,
            base_onto
        )
    add_classes(
        semicon_action_specifications,
        iof.search_one(iri=f"{IOF_IRI}ActionSpecification") if import_ontologies else base_onto.search_one(iri="*ActionSpecification"),
        base_onto
    )
    add_classes(
        semicon_sdcs,
        bfo.search_one(iri=f"{BFO_IRI}BFO_0000020") if import_ontologies else base_onto.search_one(iri="*SpecificallyDependentContinuant"),
        base_onto
    )
    add_classes(
        semicon_material_artifacts,
        iof.search_one(iri=f"{IOF_IRI}MaterialProduct") if import_ontologies else base_onto.search_one(iri="*MaterialProduct"),
        base_onto
    )
    add_classes(
        semicon_quality,
        bfo.search_one(iri=f"{BFO_IRI}BFO_0000019") if import_ontologies else base_onto.search_one(iri="*Quality"),
        base_onto
    )
    add_classes(
        semicon_process_characteristic,
        iof.search_one(iri=f"{IOF_IRI}ProcessCharacteristic") if import_ontologies else base_onto.search_one(iri="*ProcessCharacteristic"),
        base_onto
    )
    add_classes(
        semicon_measurement_ices,
        iof.search_one(iri=f"{IOF_IRI}MeasurementInformationContentEntity") if import_ontologies else base_onto.search_one(iri="*MeasurementInformationContentEntity"),
        base_onto
    )
    add_classes(
        semicon_req_ices,
        prov.search_one(iri=f"{IOF_IRI}RequirementSpecification") if import_ontologies else base_onto.search_one(iri="*RequirementSpecification"),
        base_onto
    )
    add_classes(
        semicon_activity,
        iof.search_one(iri="*Activity") if import_ontologies else base_onto.search_one(iri="*Activity"),
        base_onto
    )
    add_classes(
        manufacturing_process_concepts,
        iof.search_one(iri=f"{IOF_IRI}ManufacturingProcess") if import_ontologies else base_onto.search_one(iri="*ManufacturingProcess"),
        base_onto
    )
    add_classes(
        [fc for fc in semicon_fc_subtypes],
        base_onto.FailureCause,
        base_onto
    )

def add_base_class_types(base_classes):
    semicon_defect_concepts = list(base_classes.get("defects_and_failure_causes", {}).get("defect", []))
    semicon_quality_concepts = list(base_classes.get('semicon_quality_concepts').keys())
    semicon_characteristic_concepts = list(base_classes.get("semicon_characteristic_concepts").keys())
    failure_cause_concepts = list(base_classes.get("defects_and_failure_causes", {}).get("failure_cause", []))
    add_classes(
       semicon_quality_concepts,
       base_onto.ParameterQuality,
       base_onto
    )
    add_classes(
        semicon_characteristic_concepts,
        base_onto.ParameterCharacteristic,
        base_onto
    )
    add_classes(
       [f"{s} obs" for s in semicon_quality_concepts] + [f"{s} obs" for s in semicon_characteristic_concepts],
       base_onto.ParameterObservation,
       base_onto
    )
    add_classes(
       [f"{s} spec" for s in semicon_quality_concepts] + [f"{s} spec" for s in semicon_characteristic_concepts],
       base_onto.ParameterSpecification,
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

def resolve_entity(name, ontologies):
    entity = None
    for onto in ontologies:
        try:
            entity = onto.search_one(iri=f"*{name}")
            if not entity:
                continue
            else:
                return entity
        except AttributeError as e:
            return None

def define_properties(input_path):
    with open(input_path) as f:
        config = yaml.safe_load(f)
        if base_onto is not None:
            with base_onto: # T-Box Declaration
                search_spaces = [base_onto, iof, bfo, prov, ro]
                #------------------------------ Object Properties ----------------------------------#
                for prop in config.get("object_properties", []):
                    cls = resolve_entity(prop['name'], search_spaces)
                    if not cls:
                        bases = [ObjectProperty]
                        if prop.get('parent'):
                            entity = resolve_entity(prop['parent'], search_spaces)
                            if entity:
                                bases.append(entity)
                        if prop.get("functional"):
                            bases.append(FunctionalProperty)
                        if prop.get("transitive"):
                            bases.append(TransitiveProperty)
                        if prop.get("inverse_functional"):
                            bases.append(InverseFunctionalProperty)
                        cls = types.new_class(prop["name"], tuple(bases))
                    if "inverse_of" in prop:
                        entity = resolve_entity(prop['inverse_of'], search_spaces)
                        if entity:
                            cls.inverse_property = entity
                    if "domain" in prop:
                        entity = resolve_entity(prop['domain'], search_spaces)
                        cls.domain = [entity] if entity else []
                    if "range" in prop:
                        entity = resolve_entity(prop['range'], search_spaces)
                        cls.range = [entity] if entity else []
                    if "transitive" in prop:
                        cls.is_a.append(TransitiveProperty)

                #------------------------------ Data Properties ----------------------------------#
                for prop in config.get("data_properties", []):
                    cls = resolve_entity(prop['name'], search_spaces)
                    if not cls:
                        bases = [DataProperty]
                        if prop.get("functional"):
                            bases.append(FunctionalProperty)
                        cls = types.new_class(prop["name"], tuple(bases))
                    if "domain" in prop:
                        cls.domain = [base_onto[prop["domain"]]]
                    type_map = {"float": float, "int": int, "str": str}
                    cls.range = [type_map[prop["range"]]]
                
                for prop in config.get("annotation_properties", []):
                    cls = types.new_class(prop["name"], (AnnotationProperty,))

def add_axioms_to_ontology(axioms_dict):
    with base_onto:
        for sub_cls, axiom in axioms_dict.items():
            first_colon_index = axiom.find(":")
            axiom_type = axiom[0:first_colon_index].strip()
            axiom_text = axiom[first_colon_index:].strip()
            axiom_split_by_and = axiom_text.split("and")
            if len(axiom_split_by_and) > 1:
                axiom_split_by_and.pop(0)
                for axiom_unit in axiom_split_by_and:
                    #TODO: add generalization and support for not, only etc.
                    axiom_unit = axiom_unit.replace("(", "").replace(")", "")
                    axiom_atoms = axiom_unit.split("some")
                    axiom_atoms = [axiom_atom.strip() for axiom_atom in axiom_atoms]
                    prop, obj_cls = axiom_atoms
                    prop_atoms = prop.split(":")
                    obj_cls_atoms = obj_cls.split(":")
                    if len(prop_atoms) == 2:
                        prop_prefix, prop_name = prop_atoms
                        prop_obj = prefix_onto_map[prop_prefix].search_one(iri=f"*{prop_name}")
                    else:
                        prop_obj = base_onto[prop_atoms[0]]
                    if len(obj_cls_atoms) == 2:
                        obj_cls_prefix, obj_cls_name = obj_cls_atoms
                        obj_cls_obj = prefix_onto_map[obj_cls_prefix].search_one(iri=f"*{obj_cls_name}")
                    else:
                        obj_cls_obj = base_onto[obj_cls_atoms[0]]
                    if axiom_type.lower() == "subclassof":
                        base_onto[sub_cls].is_a.append(prop_obj.some(obj_cls_obj))
                    elif axiom_type.lower() == "equivalentto":
                        base_onto[sub_cls].equivalent_to.append(prop_obj.some(obj_cls_obj))

def add_defintions_and_examples(definitions_dict):
    with base_onto:
        for k, v in definitions_dict.items():
            # locate class or property by IRI
            ent = base_onto.search_one(iri = k)
            if ent:
                ent.definition.append(v.get('definition', ''))   # plain literal (no lang tag)
                ent.example.append(v.get('example', ''))

def add_ishikawa_causal_graph():
    def traverse_paths(graph, start, target_prop, visited=None):
        """
        Recursively traverse and print causes along 'caused_by' edges.
        """
        with base_onto:
            if visited is None:
                visited = set()

            if start in visited:
                print(f"{start} (cycle detected)")
                return
            visited.add(start)
            effect_ind = base_onto[create_classname_syntax(start)](f"{start}_1")
            if len(effect_ind.label) == 0: 
                effect_ind.label.append(f"{start}_1")
            rules = graph.get(start, {}).get("governed_by", [])
            for rule in rules:
                effect_ind.governedBy.append(rule.replace("≤", "<=").replace("≥", ">="))
            base_onto[create_classname_syntax(start)].triggeredByRuleText = rules

            causes = graph.get(start, {}).get("caused_by", [])
            for cause in causes:
                ind = base_onto[create_classname_syntax(cause)](f"{cause}_1")
                effect_ind.RO_0002559.append(ind)
                traverse_paths(graph, cause, target_prop, visited)

    with open(f"{input_path}/causal_chain.json") as f:
        cc = json.load(f)
        prop_obj = prefix_onto_map["RO"].search_one(iri=f"*RO_0002559")
        print(prop_obj)
        for defect in cc:
            traverse_paths(cc, defect, prop_obj)

def add_specs_to_ontology(specs_dict, ontology_path):
    if product1_onto is not None:
        with product1_onto:
            for si in specs_dict:
                classname = create_classname_syntax(si)
                #create spec
                spec_class = base_onto[f"{classname}Spec"]
                spec_ins = spec_class(f"{specs_dict[si]['id']}-spec")
                spec_ins.label = [f"{si} spec"]
                for value_type, value in specs_dict[si].items():
                    if value_type == "NOM":
                        spec_ins.hasNominalValue = value
                    elif value_type == "LSL":
                        spec_ins.hasLowerValue = value
                    elif value_type == "USL":
                        spec_ins.hasUpperValue = value
                    elif value_type == "onto_category":
                        onto_class = base_onto[f"{classname}"]
                        if value == "Quality":
                            onto_ins = onto_class(f"{specs_dict[si]['id']}-quality")
                            onto_ins.label = [f"{si} quality"]
                        elif value == "ProcessCharacteristic":
                            onto_ins = onto_class(f"{specs_dict[si]['id']}-processcharacteristic")
                            onto_ins.label = [f"{si} quality"]
                        spec_ins.prescribes = [onto_ins]   
            save_ontology(ontology_path)

def add_defect_individuals(
    product_individual,
    semicon_defect_concept:str
):
   if product1_onto is not None:
    with product1_onto:
        defect_classname = create_classname_syntax(semicon_defect_concept)
        onto_defect_class = base_onto[defect_classname]
        if onto_defect_class:
            product_individual_label = product_individual.label[0]
            defect_individual = onto_defect_class(f"{defect_classname}_{product_individual_label}")
            defect_individual.label.append(f"{defect_classname}_{product_individual_label}")
            product_individual.hasDefect.append(defect_individual)

def add_products_to_ontology(
    batch_size:int,
    synthetic_data_factory_file: str,
    ontology_path:str
):
    df = pd.read_csv(synthetic_data_factory_file)
    # Strip spaces from column names
    df.columns = df.columns.str.strip() # Check specs in Synthetic Data files
    if product1_onto is not None:
        product_count = 0
        with product1_onto: # A-box instantiation
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                product_individual = None
                product_label = None
                for k , v in row_dict.items():
                    if k == "PCB_ID":
                        product_individual = base_onto['PCB'](v) # start creating Product1 individuals
                        product_individual.label = [v] # assign a label
                        product_label = v
                    elif k == "Defect occured":
                        add_defect_individuals(
                            product_individual,
                            v,
                        )
                    else:
                        onto_class_syntax = create_classname_syntax(k)
                        onto_class = base_onto[onto_class_syntax]
                        if onto_class:
                            spec_class = base_onto[f"{onto_class_syntax}Spec"]
                            spec_inds = spec_class.instances()
                            if spec_inds:
                                spec_inds = spec_inds[0]
                            observation_individual =  base_onto[f"{onto_class_syntax}Obs"](  # instantiating observed value individuals for Product1
                            f"{onto_class_syntax}_{product_label}_Obs"
                            )
                            # product_individual.hasObservation.append(observation_individual)
                            observation_individual.isAbout = [spec_inds]
                            observation_individual.hasObservedValue = float(v)
                            observation_individual.observationOf = product_individual
                product_count += 1
            save_ontology(ontology_path)
            #log the number of individuals
            print(f"{product_count} product individuals imported to the ontology")

    return {"message": "products added"}
