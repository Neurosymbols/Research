import pandas as pd
import numpy as np
import re

from app.services.oracle import run_oracle
from app.services.utils import get_failure_cause_concepts

def get_defect_threshold(
        defect_matrix:pd.DataFrame,
        threshold_column:float = "rbi_score"
    ):
    def manual_percentile(data, q):
        """
        Manual percentile calculation with interpolation.
        data: list or array
        q: percentile (0-100)
        """
        data = np.sort(data)                 # 1. sort values
        N = len(data)
        
        pos = (q/100) * (N - 1)              # 2. position
        lower = int(np.floor(pos))           # 3. lower index
        upper = int(np.ceil(pos))            # 4. upper index
        weight = pos - lower                 # 5. interpolation weight

        if lower == upper:                   # exact position
            return data[lower]
        else:                                # interpolate
            return data[lower] * (1-weight) + data[upper] * weight

    def generate_threshold(rbi_scores:list):
        return manual_percentile(rbi_scores, 85)
    
    rbis = [n for n in defect_matrix[threshold_column].tolist() if n > 0]
    threshold = generate_threshold(rbis)
    print(f"threshold: {threshold}")
    defect_matrix["defect"] = (defect_matrix[threshold_column] >= threshold).astype(int)
    return threshold

def generate_blind_defect_cause_matrix(
    interaction_rules_sparql,
    specs_dict,
    failure_causes_rules_mapping,
    report_storage_path,
    rule_interaction
):
    #TODO: plan to generalize for all defects
    oracle_results = run_oracle(
        interaction_rules_sparql,
        rule_interaction
    )
    failure_cause_concepts = get_failure_cause_concepts(
        failure_causes_rules_mapping
    )
    #report 1
    rows = {}
    defect_matrix_failure_causes = {}
    defect_matrix_spec_violations = {}
    blind_defect_matrix = []
    #collect violated specs per defect instance
    for row in oracle_results['spec_violated_results']["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        if defect_label not in rows:
           rows[defect_label] = {
               'failure_causes': [], 
               'violated_specs': [],
               'flag_count': row['flagCount']['value'],
               'interaction': row['interaction']['value'],
               'rbi': 0.0
            }
        rows[defect_label]['violated_specs'].append(row["violated_spec"]["value"])
    #collect failure causes per defect instance
    for row in oracle_results['failure_causes_results']["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        print(defect_label)
        assert defect_label in rows, "inconsistent matrics getting formed"
        rows[defect_label]['failure_causes'].append(row["failure_cause"]["value"])
    #collect rbi_scores
    for row in oracle_results['rbi_results']["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        assert defect_label in rows, "inconsistent matrics getting formed"
        rows[defect_label]['rbi'] = row["rbi"]["value"]
    #keys in ascending order
    rows = {k: rows[k] for k in sorted(rows.keys(), key=lambda x: int(re.search(r"PCB(\d+)", x).group(1)))}
    for defect_label in rows:
        defect_matrix_failure_causes[defect_label] = {v['id']:1 if v['id'] in rows[defect_label]['failure_causes'] else 0 for k,v in failure_cause_concepts.items()}
    for defect_label in rows:
        defect_matrix_spec_violations[defect_label] = {k:1 if v['id'] in 
        rows[defect_label]['violated_specs'] else 0 for k,v in specs_dict.items()}
    for k,v in defect_matrix_failure_causes.items():
        # assert k in defect_matrix_spec_violations, "inconsistent matrices"
        assert k in rows, "unknown defect instance found"
        blind_defect_matrix.append({
            # **defect_matrix_spec_violations[k], 
            **v, 
            "flag_count": rows[k]['flag_count'], 
            "interaction": rows[k]['interaction'],
            'rbi': float(rows[k]['rbi'])
        })
    blind_defect_matrix_df = pd.DataFrame(blind_defect_matrix)
    get_defect_threshold(blind_defect_matrix_df, "rbi")
    blind_defect_matrix_df.to_csv(report_storage_path)