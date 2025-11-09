def test_cq3_spec_violation_report():
    query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?productlabel ?specviolated ?obsvalue ?specuppervalue ?speclowervalue ?unit
        WHERE {
            ?rootcause a term:RootCause .
            ?effect term:defectOccursOn ?product .
            ?rootcause term:affects ?product ;
                prov:wasGeneratedBy ?coa .
            ?coa term:triggeredByRule ?rule_violated ;
                term:hasAssessmentInput ?obs ;
                term:hasAssessmentInput ?spec .
            ?obs iof:isAbout ?spec.
            ?obs a iof:MeasurementInformationContentEntity .
            ?spec a iof:RequirementSpecification .
            #access labels and literals
            ?product rdfs:label ?productlabel .
            ?rootcause rdfs:label ?rootcauselabel .
            ?spec rdfs:label ?specviolated .
            ?obs rdfs:label ?obslabel .
            ?product rdfs:label ?productlabel .
            ?obs term:hasObservedValue ?obsvalue ;
                term:hasUnit ?obsunit .
            ?spec term:hasUpperValue ?specuppervalue ;
                term:hasLowerValue ?speclowervalue ;
                term:hasUnit ?unit .
            FILTER(?product = assert:PCB17)
        }
    '''

def test_cq5_coa_report():
    query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?productlabel ?effectlabel ?causelabel ?coa ?rule_violated ?parameterlabel ?obsvalue ?specuppervalue ?speclowervalue ?unit 
        (COALESCE(?correctiveaction, "Corrective action associated with root cause") AS ?correctiveactionlabel )
        WHERE {
            ?effect a term:Effect .
            ?cause a term:FailureCause .
            VALUES ?effect_pred { term:defectOccursOn term:affects }
            ?effect ?effect_pred ?product .
            ?cause term:affects ?product .
            ?effect ro:directlyCausallyInfluencedBy ?cause .
            ?cause prov:wasGeneratedBy ?coa .
            ?coa term:triggeredByRule ?rule_violated ;
                term:hasAssessmentInput ?obs ;
                term:hasAssessmentInput ?spec .
            ?obs iof:isAbout ?spec.
            ?obs iof:describes ?parameter .
            ?spec iof:prescribes ?parameter .
            ?obs a iof:MeasurementInformationContentEntity .
            ?spec a iof:RequirementSpecification .
            OPTIONAL {
            ?cause term:isCorrectedBy ?ca .
            ?ca rdfs:label ?correctiveaction
            }
            #access labels and literals
            ?product rdfs:label ?productlabel .
            ?effect rdfs:label ?effectlabel .
            ?cause rdfs:label ?causelabel .
            ?parameter rdfs:label ?parameterlabel .
            ?product rdfs:label ?productlabel .
            ?coa rdfs:label ?coalabel .
            ?obs term:hasObservedValue ?obsvalue .
            ?spec term:hasUpperValue ?specuppervalue ;
                term:hasLowerValue ?speclowervalue ;
                term:hasUnit ?unit .
            FILTER(?product = assert:PCB17)
        }
    '''

def test_cq2_corrective_actions():
    query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/core/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?product ?defect ?rootcause_label ?ca_label
        WHERE {
        ?defect a term:Defect .
        ?defect term:defectOccursOn ?product .
        ?defect ro:RO_0002559 ?rootcause .
        ?rootcause a term:RootCause .
        ?rootcause term:isCorrectedBy ?ca .
        ?ca rdfs:label ?ca_label .
        ?rootcause rdfs:label ?rootcause_label .
        FILTER(?product = assert:PCB17)
        }
    '''

def test_cq_1_causal_chain():
    query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?product ?effectlabel ?causelabel
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
            FILTER(?product = assert:PCB17)
        }
    '''

def test_disposition_quadrad():
    query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX bfo: <http://purl.obolibrary.org/obo/>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>

        SELECT ?product ?coa ?disposition ?parameterlabel ?inherer
        WHERE {
            ?coa a term:ConformanceAssessment .
            ?cause a term:RootCause .
            ?coa prov:generated ?cause .
            ?cause term:affects ?product .
            ?coa term:realizationOf ?disposition .
            ?disposition term:hasBase ?parameter .
            VALUES ?effect_pred { bfo:BFO_0000197 bfo:BFO_0000132 }
            ?parameter ?effect_pred ?inherer .
            #access labels
            ?parameter rdfs:label ?parameterlabel
            FILTER(?product = assert:PCB17)
        }
    '''