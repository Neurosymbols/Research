import pandas as pd
import re
import json
from tabulate import tabulate
from copy import copy
import numpy as np

from app.services.utils import perform_sparql_query

def fc_name_syntax(classname):
   # Split by any sequence of non-alphanumeric characters
    parts = re.split(r'[\s]+', classname)
    # Capitalize each part and join
    if len(parts) > 1:
        return "".join(word.capitalize() for word in parts if word)
    elif len(parts) == 1:
        return parts[0]

def get_data_factory():
    base_path = "./app/data"
    path = f"{base_path}/input/epoch3-7/synthetic_data_factory.csv"
    df = pd.read_csv(path)
    factory = df.to_dict(orient="records")
    return factory

def get_chain_factory():
    base_path = "./app/data"
    path = f"{base_path}/input/epoch3-7/causal_test_cases.json"
    factory = json.load(open(path))
    new_factory = {}
    for k, v in factory.items():
        new_factory[k] = []
        for chain in v:
            new_chain = []
            for chain_item in chain:
                new_chain.append(fc_name_syntax(chain_item))
            new_factory[k].append(new_chain)
    return new_factory

test_dict = {"Test Name": [], "System accuracy or response": []}

#Metric 1
def root_cause_accuracy():
    factory = get_data_factory()
    expected_set = {}
    for d in factory:
        if not pd.isna(d['Root Causes']):
            root_fcs = [fc_name_syntax(fc) for fc in d['Root Causes'].split(",")]
        else:
            root_fcs = []
        root_fcs = [fc for fc in root_fcs if fc]
        if root_fcs:
            expected_set[d['PCB_ID']] = root_fcs
    
    test_query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?productlabel ?defectlabel ?rootcauselabel ?rule
        WHERE {
            ?defect a term:Defect ;
                term:defectOccursOn ?product ;
                ro:RO_0002559 ?rootcause ;
                rdfs:label ?defectlabel .
            ?rootcause a term:RootCause ;
                    rdfs:label ?rootcauselabel ;
    				prov:wasGeneratedBy ?ca .
    		?ca term:triggeredByRule ?rule .
            ?product rdfs:label ?productlabel .
        }
        ORDER BY ?product
    '''
    result_1 = perform_sparql_query(test_query)
    result_1_bindings = result_1.get('results', {}).get('bindings', [])

    pred_set = dict()
    for b in result_1_bindings:
        plabel = b.get("productlabel").get('value')
        fclabel = b.get("rootcauselabel").get('value')
        if plabel not in pred_set:
            pred_set[plabel] = set()
        pred_set[plabel].add(fclabel)
    pred_set = {k:list(v) for k,v in pred_set.items()}

    #top-k accuracy
    total_boards_to_inspect = len(expected_set.keys())
    top_k_test_passed_boards = []
    equivalence_test_passed_boards = []
    for k,v in pred_set.items():
        #% of boards where at least one of the top-k predicted causes matches expert truth
        intersection = list(set(v).intersection(set(expected_set[k])))
        if len(intersection) > 0:
            top_k_test_passed_boards.append(k)
        #This test assesses strict semantic agreement between the system-inferred and expert-annotated root-cause sets.
        if set(v) == set(expected_set[k]):
            equivalence_test_passed_boards.append(k)
    test_dict['Test Name'].extend(["top-k root cause", "root-cause set equivalence"])
    test_dict['System accuracy or response'].extend([f"{round((len(top_k_test_passed_boards)/total_boards_to_inspect)*100,2)}%", f"{round((len(equivalence_test_passed_boards)/total_boards_to_inspect)*100,2)}%"])
    return {
       "top-k root cause": f"{round((len(top_k_test_passed_boards)/total_boards_to_inspect)*100,2)}%",
       "root-cause set equivalence": f"{round((len(equivalence_test_passed_boards)/total_boards_to_inspect)*100,2)}%"
    }


#Metric 2
def test_provenance_completeness():
    test_query = '''
        PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT (AVG(IF(BOUND(?gen) && BOUND(?der), 1, 0)) AS ?prov_completeness)
        WHERE {
        ?x a term:FailureCause .
        ?x term:affects ?product .
        ?x prov:wasGeneratedBy ?gen .
        ?gen term:triggeredByRule ?der .
        ?product a iof:MaterialProduct
        }
    '''
    result_1 = perform_sparql_query(test_query)
    result_1_bindings = result_1.get('results', {}).get('bindings', [])
    for b in result_1_bindings:
        prov_completeness = int(b.get("prov_completeness").get('value'))
    test_dict['Test Name'].extend(["provenance completeness"])
    test_dict['System accuracy or response'].extend([prov_completeness*100])
    return {
        "provenance completeness": prov_completeness*100
    }

#Metric 3
def cycle_rate():
    test_query = '''
        PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        ASK WHERE {
        ?x ro:RO_0002559+ ?x .
        }
        '''
    result_1 = perform_sparql_query(test_query)
    test_dict['Test Name'].extend(["cycle rate"])
    test_res = None
    if not result_1.get('boolean'):
        test_res = 'No cycles detected in causal chains'
        test_dict['System accuracy or response'].extend(['No cycles detected in causal chains'])
    else:
       test_res = 'cycles detected in causal chains'
       test_dict['System accuracy or response'].extend(['cycles detected in causal chains'])
    return {
       "cycle rate": test_res
    }

#Metric 4
def chain_recall():
    factory = get_chain_factory()
    test_query = '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX ro: <http://purl.obolibrary.org/obo/>

            SELECT ?productlabel ?effectlabel ?causelabel
            WHERE {
                ?effect a term:Effect .
                ?cause a term:FailureCause .
                VALUES ?effect_pred { term:defectOccursOn term:affects }
                ?effect ?effect_pred ?product .
                ?cause term:affects ?product .
                ?effect term:directlyCausallyInfluencedBy ?cause .
                ?product rdfs:label ?productlabel .
                ?effect rdfs:label ?effectlabel .
                ?cause rdfs:label ?causelabel
                FILTER(?product = assert:{PCB})
            }
        '''
    avg_recall = []
    avg_precision = []
    causal_chain_cm = []
    causal_chain_cm_ex = []
    for k,v in factory.items():
        cm = {"PCB_ID":k, "TP": -1, "TN": -1, "FP": -1, "FN": -1}
        cm_ex = {"PCB_ID":k, "TP": [], "TN": [], "FP": [], "FN": []}
        query = test_query.replace("{PCB}", k)
        result_1 = perform_sparql_query(query)
        result_1_bindings = result_1.get('results', {}).get('bindings', [])
        pred_set = []
        for b in result_1_bindings:
            # plabel = b.get("productlabel").get('value')
            effectlabel = b.get("effectlabel").get('value')
            causelabel = b.get("causelabel").get('value')
            pred_set.append((effectlabel, causelabel))
        pred_set = {tuple((i.lower() for i in item)) for item in pred_set}
        v = {tuple(i.lower() for i in item) for item in v}
        intersection = pred_set & v
        if len(v) or len(pred_set):
            recall = round((len(intersection) / len(v)) * 100, 2) if len(v) else 0
            precision = round((len(intersection)/len(pred_set))*100,2) if pred_set else 0
            cm['TP'] = len(intersection)
            cm_ex['TP'].extend(list(intersection))
            cm['FP'] = len(pred_set.difference(intersection))
            cm_ex['FP'].extend(list(pred_set.difference(intersection)))
            cm['FN'] = len(v.difference(intersection))
            cm_ex['FN'].extend(list(v.difference(intersection)))
            cm['TN'] = (len(v) + len(pred_set)) - len(intersection) - (cm['TP'] + cm['FP'] + cm['FN'])
        elif len(v) == 0 and len(pred_set) == 0:
            recall = 100
            precision = 100
            cm['TP'] = 0
            cm['FP'] = 0
            cm['FN'] = 0
            cm['TN'] = 1
        # else:
        #     recall = 0
        #     precision = 0
        causal_chain_cm.append(cm)
        causal_chain_cm_ex.append(cm_ex)
        print(f"pred set for {k} {len(list(pred_set))};;", 
              f"expected set for {k} {len(list(v))};;", 
              f"intersection set for {k} {len(list(intersection))};;",
              f"recall for {k} {recall};;",
              f"precision for {k} {precision}",
        )
        avg_recall.append(recall)
        avg_precision.append(precision)
    test_dict['Test Name'].extend(["chain recall", "chain precision"])
    test_dict['System accuracy or response'].extend([f"{round(np.mean(avg_recall),2)}%", f"{round(np.mean(avg_precision),2)}%"])
    with open("./app/data/output/epoch3-7/chain_cm_examples_report.json", "w") as f:
        json.dump(causal_chain_cm_ex, f, indent=2)
    return {
        "chain recall": f"{round(np.mean(avg_recall),2)}%",
        "chain precision": f"{round(np.mean(avg_precision),2)}%",
        "causal chain cm": causal_chain_cm
    }

# root_cause_accuracy()
# test_provenance_completeness()
# cycle_rate()
# chain_recall()

# print(tabulate(test_dict, headers="keys", tablefmt="github"))