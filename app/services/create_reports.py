import pandas as pd
import re

from app.services.oracle import run_oracle
from app.services.utils import perform_sparql_query, get_failure_cause_concepts

def create_reports(
    interaction_rules_sparql,
    specs_dict,
    failure_causes_rules_mapping,
    report_storage_path
):
    #TODO: plan to generalize for all defects
    oracle_results = run_oracle(
        interaction_rules_sparql
    )
    failure_cause_concepts = get_failure_cause_concepts(
        failure_causes_rules_mapping
    )
    defect_results = perform_sparql_query(
        '''
           PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

            SELECT ?defectLabel ?hasDefect
            WHERE {
            
            ?defect a base:SolderBridging .
            ?defect rdfs:label ?defectLabel .

            OPTIONAL { ?defect base:flagCount        ?fc . }
            OPTIONAL { ?defect base:interactionBonus ?ib . }

            # Normalize missing values to 0 and compute the flag
            BIND( xsd:decimal(COALESCE(?fc, 0)) AS ?fcN )
            BIND( xsd:decimal(COALESCE(?ib, 0)) AS ?ibN )
            BIND( IF( (?fcN >= 2) || (?ibN > 1), 1, 0 ) AS ?hasDefect )
            }
        '''
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
               'defect': 0,
               'rbi': 0.0
        }
        rows[defect_label]['violated_specs'].append(row["violated_spec"]["value"])
    #collect failure causes per defect instance
    for row in oracle_results['failure_causes_results']["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        assert defect_label in rows, "inconsistent matrics getting formed"
        rows[defect_label]['failure_causes'].append(row["failure_cause"]["value"])
    #collect rbi_scores
    for row in oracle_results['rbi_results']["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        assert defect_label in rows, "inconsistent matrics getting formed"
        rows[defect_label]['rbi'] = row["rbi"]["value"]
    #collect defects
    for row in defect_results["results"]["bindings"]:
        defect_label = row["defectLabel"]["value"]
        assert defect_label in rows, "inconsistent matrics getting formed"
        rows[defect_label]['defect'] = row["hasDefect"]["value"]
    #keys in ascending order
    rows = {k: rows[k] for k in sorted(rows.keys(), key=lambda x: int(re.search(r"PCB(\d+)", x).group(1)))}
    for defect_label in rows:
        defect_matrix_failure_causes[defect_label] = {v['id']:1 if v['id'] in rows[defect_label]['failure_causes'] else 0 for k,v in failure_cause_concepts.items()}
    for defect_label in rows:
        defect_matrix_spec_violations[defect_label] = {k:1 if v['id'] in 
        rows[defect_label]['violated_specs'] else 0 for k,v in specs_dict.items()}
    for k,v in defect_matrix_failure_causes.items():
        assert k in defect_matrix_spec_violations, "inconsistent matrices"
        assert k in rows, "unknown defect instance found"
        blind_defect_matrix.append({
            **defect_matrix_spec_violations[k], 
            **v, 
            "flag_count": rows[k]['flag_count'], 
            "interaction": rows[k]['interaction'],
            'defect': rows[k]['defect'],
            'rbi': rows[k]['rbi']
        })
    blind_defect_matrix_df = pd.DataFrame(blind_defect_matrix)
    blind_defect_matrix_df.to_csv(report_storage_path)