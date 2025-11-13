import pandas as pd
import pytest

from app.services.utils import perform_sparql_query, clear_graphdb_default_graph, export_ontology_to_graphdb
from app.services.causal_chains import rule_to_sparql, fire_failure_cause_queries
from app.services.utils import create_classname_syntax


@pytest.fixture(scope="session")
def data_factory():
    base_path = "./app/data"
    path = f"{base_path}/input/epoch3-7/synthetic_data_factory.csv"
    df = pd.read_csv(path)
    factory = df.to_dict(orient="records")
    return factory

def test_firing_of_failure_cause_rules_from_ishikawa_causal_graph():
    conformance_count_query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT (COUNT(?conformance) AS ?count)
        WHERE {
        ?conformance a term:ConformanceAssessment .
        }
    '''
    conformance_with_required_edges_count = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT (COUNT(DISTINCT ?conformance) AS ?count)
        WHERE {
        ?conformance a term:ConformanceAssessment .
        ?conformance prov:generated ?generated .
        ?conformance term:hasAssessmentInput ?input .
        ?conformace term:triggeredByRule ?rule .
        }
    '''
    result_1 = perform_sparql_query(conformance_count_query)
    result_2 = perform_sparql_query(conformance_with_required_edges_count)

    result_1_bindings = result_1.get('results', {}).get('bindings', [])
    result_2_bindings = result_2.get('results', {}).get('bindings', [])
    assert len(result_1_bindings) > 0
    assert len(result_2_bindings) > 0

    assert result_1_bindings[0].get('count') == result_2_bindings[0].get('count')

# def test_predictability_of_firing_rules():
#     conformance_count_query = '''
#         PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
#         PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
#         PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
#         PREFIX bfo: <http://purl.obolibrary.org/obo/>
#         PREFIX prov: <http://www.w3.org/ns/prov#>
#         PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
#         PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

#         SELECT (COUNT(?conformance) AS ?count)
#         WHERE {
#         ?conformance a term:ConformanceAssessment .
#         }
#     '''
#     run1_result1 = perform_sparql_query(conformance_count_query)
#     run1_result1_bindings = run1_result1.get('results', {}).get('bindings', [])
#     run1_result1_count = run1_result1_bindings[0].get('count')

#     base_path = "./app/data"
#     path = f"{base_path}/ontologies/epoch3-7"
#     clear_graphdb_default_graph()
#     ontology_paths = [
#         f"{path}/bfo-prov.owl",
#         f"{path}/iof-core.rdf",
#         f"{path}/ro-causal-properties.owl",
#         f"{path}/causal-terminology.owl",
#         f"{path}/causal-assertions.owl"
#     ]
#     export_ontology_to_graphdb(
#         ontology_paths
#     )
#     rule_to_sparql(verb="INSERT")
#     fire_failure_cause_queries(verb="INSERT")

#     run2_result1 = perform_sparql_query(conformance_count_query)
#     run2_result1_bindings = run2_result1.get('results', {}).get('bindings', [])
#     run2_result1_count = run2_result1_bindings[0].get('count')

#     assert run1_result1_count == run2_result1_count

def test_failure_cause_generation(data_factory):
    factory = data_factory
    expected_set = {}
    for d in factory:
        if not pd.isna(d['Mechanism Failure Causes']):
            mech_fcs = [create_classname_syntax(fc) for fc in d['Mechanism Failure Causes'].split(",")]
        else:
            mech_fcs = []
        if not pd.isna(d['Root Causes']):
            root_fcs = [create_classname_syntax(fc) for fc in d['Root Causes'].split(",")]
        else:
            root_fcs = []
        total_fcs = mech_fcs + root_fcs
        total_fcs = [fc for fc in total_fcs if fc]
        expected_set[d['PCB_ID']] = total_fcs
    
    test_query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?productlabel ?failurecauselabel
        WHERE {
            ?failurecause a term:FailureCause ;
                        term:affects ?product ;
                        rdfs:label ?failurecauselabel ;
                        prov:wasGeneratedBy ?coa .
            ?product a iof:MaterialProduct ;
                    rdfs:label ?productlabel .
        }
        ORDER BY ?product
    '''
    result_1 = perform_sparql_query(test_query)
    result_1_bindings = result_1.get('results', {}).get('bindings', [])

    pred_set = dict()
    for b in result_1_bindings:
        plabel = b.get("productlabel").get('value')
        fclabel = b.get("failurecauselabel").get('value')
        if plabel not in pred_set:
            pred_set[plabel] = set()
        pred_set[plabel].add(fclabel)
    pred_set = {k:list(v) for k,v in pred_set.items()}

    for k,v in pred_set.items():
        assert set(expected_set[k]) == set(v)

def test_root_cause_detection(data_factory):
    factory = data_factory
    expected_set = {}
    for d in factory:
        if not pd.isna(d['Root Causes']):
            root_fcs = [create_classname_syntax(fc) for fc in d['Root Causes'].split(",")]
        else:
            root_fcs = []
        root_fcs = [fc for fc in root_fcs if fc]
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

        SELECT ?productlabel ?defectlabel ?rootcauselabel
        WHERE {
            ?defect a term:Defect ;
                term:defectOccursOn ?product ;
                ro:RO_0002559 ?rootcause ;
                rdfs:label ?defectlabel .
            ?rootcause a term:RootCause ;
                    rdfs:label ?rootcauselabel .
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

    for k,v in pred_set.items():
        assert set(expected_set[k]) == set(v)

def test_corrective_actions_assignment(data_factory):
    factory = data_factory
    expected_set = {}
    for d in factory:
        if not pd.isna(d['Corrective Actions']):
            cas = [ca.lower().strip() for ca in d['Corrective Actions'].split(",")]
        else:
            cas = []
        expected_set[d['PCB_ID']] = cas

    test_query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?productlabel ?defectlabel ?rootcauselabel ?calabel
        WHERE {
            ?defect a term:Defect ;
                term:defectOccursOn ?product ;
                ro:RO_0002559 ?rootcause ;
                rdfs:label ?defectlabel .
            ?rootcause a term:RootCause ;
                    rdfs:label ?rootcauselabel ;
                    term:isCorrectedBy ?ca .
            ?product rdfs:label ?productlabel .
            ?ca rdfs:label ?calabel
        }
        ORDER BY ?product
    '''
    result_1 = perform_sparql_query(test_query)
    result_1_bindings = result_1.get('results', {}).get('bindings', [])

    pred_set = dict()
    for b in result_1_bindings:
        plabel = b.get("productlabel").get('value')
        calabel = b.get("calabel").get('value').lower()
        if plabel not in pred_set:
            pred_set[plabel] = set()
        pred_set[plabel].add(calabel)
    pred_set = {k:list(v) for k,v in pred_set.items()}

    for k,v in pred_set.items():
        assert set(expected_set[k]) == set(v)