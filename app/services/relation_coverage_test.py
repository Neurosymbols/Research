from app.services.utils import perform_sparql_query

PREFIXES = '''
    PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
    PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
    PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
    PREFIX BFO: <http://purl.obolibrary.org/obo/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX RO: <http://purl.obolibrary.org/obo/>
'''
#### Process Characteristics and Quality
relation_queries = [
"""
    ASK WHERE {
    ?measurement a iof:MeasurementInformationContentEntity .
    ?spec a iof:RequirementSpecification .
    ?quality a BFO:BFO_0000019 .
    ?measurement iof:describes ?quality .
    ?spec iof:prescribes ?quality .
    ?measurement iof:isAbout ?spec
    }
""",
    """
ASK WHERE {
  ?measurement a iof:MeasurementInformationContentEntity .
  ?spec a iof:RequirementSpecification .
  ?pc a iof:ProcessCharacteristic .
  ?measurement iof:describes ?pc .
  ?spec iof:prescribes ?pc .
  ?measurement iof:isAbout ?spec
}
""",
"""
ASK WHERE {
  ?spec a iof:RequirementSpecification . 
  ?doc a term:PlanSpecification .
  ?spec prov:wasDerivedFrom ?doc .
}
""",
#equipment and material product
"""
ASK WHERE {
  ?equipment a iof:PieceOfEquipment .
  ?process a iof:PlannedProcess .
  ?equipment BFO:BFO_0000056 ?process .
}
""",
"""
ASK WHERE {
  ?material a iof:MaterialProduct .
  ?process a iof:PlannedProcess .
  ?material BFO:BFO_0000056 ?process .
}
""",
# quality disposition Quadrad
"""
ASK WHERE {
  ?fc a term:FailureCause .
  ?quality a BFO:BFO_0000019 .
  ?qualityDisposition a BFO:BFO_0000016 .
  ?coa a term:ConformanceAssessment .
  ?material a iof:MaterialProduct .

  ?quality term:baseOf ?qualityDisposition .
  ?qualityDisposition term:hasRealization ?coa .
  ?quality BFO:BFO_0000197 ?material .
  ?qualityDisposition BFO:BFO_0000197 ?material .
  ?quality term:hasDeviation ?fc 
}
""",
#process characteristic disposition quadrad
"""
ASK WHERE {
  ?fc a term:FailureCause .
  ?pc a iof:ProcessCharacteristic .
  ?pcDisposition a BFO:BFO_0000016 .
  ?coa a term:ConformanceAssessment .
  ?process a iof:PlannedProcess .

  ?pc term:baseOf ?pcDisposition .
  ?pcDisposition term:hasRealization ?coa .
  ?pc BFO:BFO_0000132 ?process .
  ?pcDisposition RO:RO_0000052 ?process .
  ?pc term:hasDeviation ?fc
}
""",
# failurecause
"""
ASK WHERE {
    ?fc a term:FailureCause .
    ?material a iof:MaterialProduct .
    ?coa a term:ConformanceAssessment .
    ?ca a term:CorrectiveAction .

    ?fc term:correctedBy ?ca .
    ?fc term:affecs ?material .
    ?fc prov:isGeneratedBy ?coa .
}
"""
]


def test_relation_queries():
    d = {}
    id = 1
    for query in relation_queries:
        query_id = f"QUERY {id}"
        add_prefix = f"{PREFIXES} \n\n {query}"
        query_res = perform_sparql_query(add_prefix)
        d[query_id] = query_res.get('boolean')
        id += 1
    print(d)
test_relation_queries()
