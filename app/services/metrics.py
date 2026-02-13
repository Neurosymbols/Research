import pandas as pd
import re
import json
from tabulate import tabulate
from copy import copy
import numpy as np
import math

from app.services.utils import perform_sparql_query
from app.config.onto_config import products_in_ontology

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
    path = f"{base_path}/input/epoch3-7/synthetic_data_factory_5.csv"
    df = pd.read_csv(path)
    def is_empty(x):
        return pd.isna(x) or str(x).strip() == "" or str(x).strip() == "No Defect"

    def is_not_empty(x):
        return not is_empty(x)
    mask = (
        df["Defect"].apply(is_not_empty) |
        (
            df["Defect"].apply(is_empty) &
            (
                df["mech causes"].apply(is_not_empty) |
                df["root causes"].apply(is_not_empty)
            )
        )
    )
    df = df[mask].head(products_in_ontology)
    factory = df.to_dict(orient="records")
    print(len(factory))
    return factory

def get_chain_factory():
    base_path = "./app/data"
    path = f"{base_path}/input/epoch3-7/test_chains_3.json"
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

test_dict = {"Test Name": [], "System accuracy or response": [], "Interpretation": []}

#Metric 1
def root_cause_accuracy():
    factory = get_data_factory()
    expected_set = {}
    for d in factory:
        root_fcs = []
        #consider root cause even if defect occurs or not
        if not pd.isna(d['root causes']):
            root_fcs = [fc_name_syntax(fc) for fc in d['root causes'].split(";")]
            root_fcs = [fc for fc in root_fcs if fc]
            expected_set[d['PCB_ID']] = root_fcs
        else:
            #consider mechanism failure causes as root causes
            if not pd.isna(d['mech causes']):
                mech_fcs = [fc_name_syntax(fc) for fc in d['mech causes'].split(";")]
                root_fcs.extend(mech_fcs)
                root_fcs = [fc for fc in root_fcs if fc]
                expected_set[d['PCB_ID']] = root_fcs
    print(f"expected set length {len(expected_set.keys())}")
    
    test_query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?productlabel ?rootcauselabel ?prob
        WHERE {
            ?rootcause a term:RootCause ;
                    rdfs:label ?rootcauselabel ;
    				term:affects ?product .
    		OPTIONAL {
                ?rootcause prov:wasGeneratedBy ?ca .
                ?ca term:hasProbability ?prob .
    		}
            OPTIONAL {
        		?rootcause term:hasProbability ?prob .
            }
            ?product rdfs:label ?productlabel .
        }
        ORDER BY ?product
    '''
    result_1 = perform_sparql_query(test_query)
    result_1_bindings = result_1.get('results', {}).get('bindings', [])

    pred_set = dict()
    pred_set_with_prob = dict()
    for b in result_1_bindings:
        plabel = b.get("productlabel").get('value')
        fclabel = b.get("rootcauselabel").get('value')
        prob_value = float(b.get("prob", {}).get('value', 0.0))
        if plabel not in pred_set:
            pred_set[plabel] = set()
            pred_set_with_prob[plabel] = dict()
        if fclabel not in ["NoPrintingMech", "NoReflowMech"]:
            pred_set[plabel].add(fclabel)
            pred_set_with_prob[plabel][fclabel] = prob_value
    pred_set = {k:list(v) for k,v in pred_set.items()}

    total_boards = len(expected_set)

    hit_rate_boards = []
    exact_match_boards = []
    jaccard_scores = []
    mrr_scores = []

    data = []

    for pcb_id, expected_causes in expected_set.items():
        set_expected = {item.lower() for item in expected_causes}
        set_pred = {item.lower() for item in pred_set.get(pcb_id, [])}
        data.append({
            "id": pcb_id, 
            "expected": list(expected_causes), 
            "predicted": list(pred_set.get(pcb_id, []))
        })
        d = pred_set_with_prob.get(pcb_id, {})
        max_root_cause = max(d, key=d.get) if d else ""
        rank = expected_causes.index(max_root_cause) if max_root_cause in expected_causes else math.inf
        mrr = 1/(rank+1)
        mrr_scores.append(mrr)

        intersection = set_expected & set_pred
        union = set_expected | set_pred

        # 1️⃣ Hit Rate: at least one correct root cause
        if intersection:
            hit_rate_boards.append(pcb_id)

        # 2️⃣ Exact Match: strict set equality
        if set_pred == set_expected:
            exact_match_boards.append(pcb_id)

        # 3️⃣ Jaccard Similarity (soft agreement)
        jaccard = len(intersection) / len(union) if union else 1.0
        jaccard_scores.append(jaccard)

        # Debug print (optional)
        # print(
        #     pcb_id,
        #     f"pred: {list(set_pred)}",
        #     f"expec: {list(set_expected)}",
        #     f"hit: {bool(intersection)}",
        #     f"exact_match: {set_pred == set_expected}",
        #     f"jaccard: {round(jaccard * 100, 2)}%"
        # )

    # -----------------------------
    # Aggregate metrics
    # -----------------------------
    hit_rate_pct = round(len(hit_rate_boards) / total_boards * 100, 2)
    exact_match_pct = round(len(exact_match_boards) / total_boards * 100, 2)
    avg_jaccard_pct = round(sum(jaccard_scores) / total_boards * 100, 2)
    avg_mrr = round(sum(mrr_scores) / total_boards, 2)

    # -----------------------------
    # Populate results table
    # -----------------------------
    test_dict['Test Name'].extend([
        "Hit Rate (≥1 correct)",
        "Jaccard Similarity (%)",
        "Exact Match Accuracy",
        "Mean Reciprocal Rank"
    ])

    test_dict['System accuracy or response'].extend([
        f"{hit_rate_pct}%",
        f"{avg_jaccard_pct}%",
        f"{exact_match_pct}%",
        avg_mrr
    ])

    test_dict['Interpretation'].extend([
        "Did the system get on the right path?",
        "How close is the system reasoning to the expert?",
        "How often is the system perfectly aligned with the expert?",
        "How quickly the most dominant ground-truth cause appears"
    ])

    with open("./root_cause_match.json", "w") as f:
        json.dump(data, f , indent =2)

    return {
        "Hit Rate (≥1 correct)": f"{hit_rate_pct}%",
        "Jaccard Similarity (%)": f"{avg_jaccard_pct}%",
        "Exact Match Accuracy": f"{exact_match_pct}%",
        "Mean Reciprocal Rank": avg_mrr
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
    test_dict['Interpretation'].extend([
        "Are the generated explanations structurally valid?"
    ])
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
                ?effect ro:directlyCausallyInfluencedBy ?cause .
                ?product rdfs:label ?productlabel .
                ?effect rdfs:label ?effectlabel .
                ?cause rdfs:label ?causelabel
                FILTER(?product = assert:{PCB})
            }
        '''
    avg_recall = []
    avg_precision = []
    causal_chain_cm = []
    recall_data = {}
    prec_data = {}
    i = 0
    chain_data = []
    for k,v in factory.items():
        recall_data[k] = 0.0
        prec_data[k] = 0.0
        cm = {"PCB_ID":k, "TP": -1, "TN": -1, "FP": -1, "FN": -1}
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
        # print(pred_set)
        v = {tuple(i.lower() for i in item) for item in v}
        # print(v)
        intersection = pred_set & v
        chain_data.append({"id": k, "expected": list(v), "predicted": list(pred_set)})
        if len(v) or len(pred_set):
            recall = round((len(intersection) / len(v)) * 100, 2) if len(v) else 0
            precision = round((len(intersection)/len(pred_set))*100,2) if pred_set else 0
            cm['TP'] = len(intersection)
            cm['FP'] = len(pred_set.difference(intersection))
            cm['FN'] = len(v.difference(intersection))
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
        print(f"pred set for {k} {len(list(pred_set))};;", 
              f"expected set for {k} {len(list(v))};;", 
              f"intersection set for {k} {len(list(intersection))};;",
              f"recall for {k} {recall};;",
              f"precision for {k} {precision}",
        )
        avg_recall.append(recall)
        avg_precision.append(precision)
        recall_data[k] = recall
        prec_data[k] = precision
    test_dict['Test Name'].extend(["chain recall", "chain precision"])
    test_dict['System accuracy or response'].extend([f"{round(np.mean(avg_recall),2)}%", f"{round(np.mean(avg_precision),2)}%"])
    test_dict['Interpretation'].extend([
        "How close is the system reasoning to the expert?",
        "How often is the system perfectly aligned with the expert?"
    ])
    with open("./chain_match.json", "w") as f:
        json.dump(chain_data, f , indent =2)
    return {
        "chain recall": f"{round(np.mean(avg_recall),2)}%",
        "chain precision": f"{round(np.mean(avg_precision),2)}%",
        "causal chain cm": causal_chain_cm,
        "recall data": recall_data,
        "prec data": prec_data,
        "sigma recall": str(round(float(np.array(avg_recall).std()), 2)),
        "min recall":   str(round(float(np.array(avg_recall).min()), 2)),
        "max recall":   str(round(float(np.array(avg_recall).max()), 2)),
        "sigma prec":   str(round(float(np.array(avg_precision).std()), 2)),
        "min prec":     str(round(float(np.array(avg_precision).min()), 2)),
        "max prec":     str(round(float(np.array(avg_precision).max()), 2))
    }

root_cause_accuracy()
# test_provenance_completeness()
cycle_rate()
chain_recall()

print(tabulate(test_dict, headers="keys", tablefmt="github"))