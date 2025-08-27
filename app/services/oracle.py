from ..utils import perform_sparql_update, perform_sparql_query

def run_oracle(interaction_rules):
    #assigns flagcount
    perform_sparql_update(
        '''
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            DELETE {
            ?defect base:flagCount ?oldCount .
            }
            INSERT {
            ?defect base:flagCount ?countTyped .
            }
            WHERE {
            {
                SELECT ?defect (xsd:integer(COUNT(?fc)) AS ?countTyped)
                WHERE {
                ?defect base:hasFailureCause ?fc .
                }
                GROUP BY ?defect
            }

            OPTIONAL {
                ?defect base:flagCount ?oldCount .
            }
            }
        '''
    )
    #assign interaction score
    perform_sparql_update(
        f'''
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            DELETE {{?defect base:interactionBonus ?oldBonus .}}
            INSERT {{?defect base:interactionBonus ?finalScore . }}
            WHERE {{
                ?defect a base:SolderBridging .
                OPTIONAL {{ ?defect base:interactionBonus ?oldBonus . }}
                BIND (
                  (
                    {interaction_rules}
                  ) as ?finalScore
                ) 
            }}  
        '''
    )

    spec_violated_results = perform_sparql_query(
        '''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?defectLabel (COALESCE(?sp, 0) AS ?violated_spec) ?flagCount ?interaction
            WHERE {
                ?defect a base:SolderBridging ;
                        rdfs:label ?defectLabel;
                        base:flagCount ?flagCount;
                        base:interactionBonus ?interaction .


            OPTIONAL {
                ?defect base:violatesSpecification ?spec .
                ?spec rdfs:label ?sp .
                
                }
            }
            ORDER BY ?defect
        '''
    )
    fc_results = perform_sparql_query(
        '''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX product1: <https://abakai.ai/data/semicon-product1.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?defectLabel (COALESCE(?fc, 0) AS ?failure_cause)
            WHERE {
                ?defect a base:SolderBridging ;
                        rdfs:label ?defectLabel;


            OPTIONAL {
                ?defect base:hasFailureCause ?failurecause .
                ?failurecause rdfs:label ?fc .
                
                }
            }
            ORDER BY ?defect
        '''
    )
    rbi_results = perform_sparql_query(
        '''
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX base: <https://abakai.ai/ontology/semicon-base.owl#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?defectLabel ?rbi
            WHERE{
                ?defect rdfs:label ?defectLabel
                {SELECT ?defect (SUM(?part) AS ?base)
                    WHERE {
                    ?defect a base:SolderBridging .
                    OPTIONAL {
                        ?defect base:hasFailureCause ?fc .
                        ?fc     base:hasSeverity ?sev ;
                                base:hasWeight   ?w .
                    }
                    BIND(IF(BOUND(?sev) && BOUND(?w),
                            xsd:decimal(?sev) * xsd:decimal(?w),
                            0) AS ?part)
                    }
                GROUP BY ?defect}
                {SELECT ?defect ?bPart
                    WHERE {
                        ?defect a base:SolderBridging .      
                    OPTIONAL { ?defect base:interactionBonus ?b . }
                    BIND(IF(BOUND(?b), xsd:decimal(?b), 0) AS ?bPart)
                    }
                }
                BIND( xsd:decimal(COALESCE(?base, 0)) + xsd:decimal(COALESCE(?bPart, 0)) AS ?rbi )
            }
        '''
    )
    return {
        "spec_violated_results": spec_violated_results,
        "failure_causes_results": fc_results,
        "rbi_results": rbi_results
    }