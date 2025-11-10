ishikawa_queries = {
    "solder_printing_stage": {
        "paste_volume_fc_query": '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If PasteVolumePerAperture > PasteVolumePerAperture_USL == ExcessPasteVolumePerAperture" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?PasteVolumePerAperture_obs ;
                        term:hasAssessmentInput ?PasteVolumePerAperture_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:ExcessPasteVolumePerAperture ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .
            } WHERE {
            ?effect a term:SolderBridging .
            ?disposition a term:ExcessPasteVolumePerApertureDisposition .
            ?PasteVolumePerAperture_obs a term:PasteVolumePerApertureObs ;
                                                    term:hasObservedValue ?PasteVolumePerAperture_obsvalue ;
                                                    iof:isAbout ?PasteVolumePerAperture_spec ;
                                                    term:observationOf ?product .
                                        ?PasteVolumePerAperture_spec a term:ParameterSpecification . 
                                    
            ?PasteVolumePerAperture_spec term:hasUpperValue ?PasteVolumePerAperture_specvalue .
            ?effect term:defectOccursOn ?product .
            FILTER(xsd:float(?PasteVolumePerAperture_obsvalue) > xsd:float(?PasteVolumePerAperture_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'ExcessPasteVolumePerAperture-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'ExcessPasteVolumePerAperture-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "ExcessPasteVolumePerAperture-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("ExcessPasteVolumePerAperture") AS ?fc_label)
            }
        ''',
        'aperture_overfill_fc_rule_1_query': '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If StencilThickness > StencilThickness_USL OR ApertureAreaRatio < ApertureAreaRatio_LSL == ApertureOverfill" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?ApertureAreaRatio_obs ;
                        term:hasAssessmentInput ?ApertureAreaRatio_spec ;
                
            term:hasAssessmentInput ?StencilThickness_obs ;
                        term:hasAssessmentInput ?StencilThickness_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:ApertureOverfill ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .
            } WHERE {
            ?effect a term:ExcessPasteVolumePerAperture .
            ?disposition a term:ApertureOverfillDisposition .
            ?ApertureAreaRatio_obs a term:ApertureAreaRatioObs ;
                                                    term:hasObservedValue ?ApertureAreaRatio_obsvalue ;
                                                    iof:isAbout ?ApertureAreaRatio_spec ;
                                                    term:observationOf ?product .
                                        ?ApertureAreaRatio_spec a term:ParameterSpecification . 
                                    

        ?StencilThickness_obs a term:StencilThicknessObs ;
                                                    term:hasObservedValue ?StencilThickness_obsvalue ;
                                                    iof:isAbout ?StencilThickness_spec ;
                                                    term:observationOf ?product .
                                        ?StencilThickness_spec a term:ParameterSpecification . 
                                    
            ?ApertureAreaRatio_spec term:hasLowerValue ?ApertureAreaRatio_specvalue .
            ?StencilThickness_spec term:hasUpperValue ?StencilThickness_specvalue .
            ?effect term:affects ?product .
            FILTER(xsd:float(?ApertureAreaRatio_obsvalue) < xsd:float(?ApertureAreaRatio_specvalue) || xsd:float(?StencilThickness_obsvalue) > xsd:float(?StencilThickness_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'ApertureOverfill-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'ApertureOverfill-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "ApertureOverfill-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("ApertureOverfill") AS ?fc_label)
            }
        ''',
        'aperture_overfill_fc_rule_2_query': '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If SqueegeeAngle < SqueegeeAngle_LSL AND SqueegeeSpeed < SqueegeeSpeed_LSL == ApertureOverfill" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?SqueegeeAngle_obs ;
                        term:hasAssessmentInput ?SqueegeeAngle_spec ;
                
            term:hasAssessmentInput ?SqueegeeSpeed_obs ;
                        term:hasAssessmentInput ?SqueegeeSpeed_spec ;
                
            term:hasAssessmentInput ?SqueegeePressure_obs ;
                        term:hasAssessmentInput ?SqueegeePressure_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:ApertureOverfill ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .
            } WHERE {
            ?effect a term:ApertureOverfill .
            ?disposition a term:ApertureOverfillDisposition .
            ?SqueegeeAngle_obs a term:SqueegeeAngleObs ;
                                                    term:hasObservedValue ?SqueegeeAngle_obsvalue ;
                                                    iof:isAbout ?SqueegeeAngle_spec ;
                                                    term:observationOf ?product .
                                        ?SqueegeeAngle_spec a term:ParameterSpecification . 
                                    

            ?SqueegeeSpeed_obs a term:SqueegeeSpeedObs ;
                                                    term:hasObservedValue ?SqueegeeSpeed_obsvalue ;
                                                    iof:isAbout ?SqueegeeSpeed_spec ;
                                                    term:observationOf ?product .
                                        ?SqueegeeSpeed_spec a term:ParameterSpecification . 
                                                          
            ?SqueegeeAngle_spec term:hasLowerValue ?SqueegeeAngle_specvalue .
            ?SqueegeeSpeed_spec term:hasLowerValue ?SqueegeeSpeed_specvalue .
            ?effect term:affects ?product .
            FILTER(xsd:float(?SqueegeeAngle_obsvalue) < xsd:float(?SqueegeeAngle_specvalue) && xsd:float(?SqueegeeSpeed_obsvalue) < xsd:float(?SqueegeeSpeed_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'ApertureOverfill-rule-2')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'ApertureOverfill-rule-2') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "ApertureOverfill-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("ApertureOverfill") AS ?fc_label)
            }
        ''',
        'aperture_area_ratio_fc_query': '''
                PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
                PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
                PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
                PREFIX bfo: <http://purl.obolibrary.org/obo/>
                PREFIX prov: <http://www.w3.org/ns/prov#>
                PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                CONSTRUCT { 
                ?coa a term:ConformanceAssessment ;
                    term:triggeredByRule "If ApertureAreaRatio < ApertureAreaRatio_LSL == LowAreaRatio" ;
                    term:realizationOf ?disposition ;
                    term:hasAssessmentInput ?ApertureAreaRatio_obs ;
                            term:hasAssessmentInput ?ApertureAreaRatio_spec ;
                    
                    rdfs:label ?coa_label .
                ?fc a term:LowAreaRatio, term:RootCause ;
                    prov:wasGeneratedBy ?coa ;
                    term:affects ?product ;
                    rdfs:label ?fc_label .
                ?effect term:directlyCausallyInfluencedBy ?fc .
                
                ?action a term:CorrectiveAction ;
                    rdfs:label ?action_label .
                ?fc term:isCorrectedBy ?action .
                } WHERE {
                ?effect a term:ApertureOverfill .
                ?disposition a term:LowAreaRatioDisposition .
                ?ApertureAreaRatio_obs a term:ApertureAreaRatioObs ;
                                                        term:hasObservedValue ?ApertureAreaRatio_obsvalue ;
                                                        iof:isAbout ?ApertureAreaRatio_spec ;
                                                        term:observationOf ?product .
                                            ?ApertureAreaRatio_spec a term:ParameterSpecification . 
                                        
                ?ApertureAreaRatio_spec term:hasLowerValue ?ApertureAreaRatio_specvalue .
                ?effect term:affects ?product .
                FILTER(xsd:float(?ApertureAreaRatio_obsvalue) < xsd:float(?ApertureAreaRatio_specvalue))
                BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'LowAreaRatio-rule-1')) AS ?coa)
                BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'LowAreaRatio-rule-1') AS ?coa_label)
                BIND(IRI(CONCAT(str(assert:), "FC-", "LowAreaRatio-", STRAFTER(STR(?product), "#"))) AS ?fc)
                BIND(CONCAT("LowAreaRatio") AS ?fc_label)
                }
        ''',
        'stencil_thickness_fc_query': '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If StencilThickness > StencilThickness_USL == StencilThicknessTooHigh" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?StencilThickness_obs ;
                        term:hasAssessmentInput ?StencilThickness_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:StencilThicknessTooHigh, term:RootCause ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
                ?effect term:directlyCausallyInfluencedBy ?fc .

            ?action a term:CorrectiveAction ;
                rdfs:label ?action_label .
            ?fc term:isCorrectedBy ?action .
                } WHERE {
                ?effect a term:ApertureOverfill .
                ?disposition a term:StencilThicknessTooHighDisposition .
                ?StencilThickness_obs a term:StencilThicknessObs ;
                                                    term:hasObservedValue ?StencilThickness_obsvalue ;
                                                    iof:isAbout ?StencilThickness_spec ;
                                                    term:observationOf ?product .
                                        ?StencilThickness_spec a term:ParameterSpecification . 
                                    
            ?StencilThickness_spec term:hasUpperValue ?StencilThickness_specvalue .
            ?effect term:affects ?product .
            FILTER(xsd:float(?StencilThickness_obsvalue) > xsd:float(?StencilThickness_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'StencilThicknessTooHigh-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'StencilThicknessTooHigh-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "StencilThicknessTooHigh-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("StencilThicknessTooHigh") AS ?fc_label)
            BIND(IRI(CONCAT(str(assert:), "CA-", "FC-", "StencilThicknessTooHigh-", STRAFTER(STR(?product), "#"))) AS ?action)
            BIND("Use thinner foil/step-down; reduce aperture size; apply nano-coating" as ?action_label)
            }
        ''',
        'squeegee_speed_fc_query': '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If SqueegeeSpeed < SqueegeeSpeed_LSL == SqueegeeSpeedTooLow" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?SqueegeeSpeed_obs ;
                        term:hasAssessmentInput ?SqueegeeSpeed_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:SqueegeeSpeedTooLow, term:RootCause ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .

            ?action a term:CorrectiveAction ;
                    rdfs:label ?action_label .
            ?fc term:isCorrectedBy ?action .
            } WHERE {
            ?effect a term:ApertureOverfill .
            ?disposition a term:SqueegeeSpeedTooLowDisposition .
            ?SqueegeeSpeed_obs a term:SqueegeeSpeedObs ;
                                                    term:hasObservedValue ?SqueegeeSpeed_obsvalue ;
                                                    iof:isAbout ?SqueegeeSpeed_spec ;
                                                    term:observationOf ?product .
                                        ?SqueegeeSpeed_spec a term:ParameterSpecification . 
                                    
            ?SqueegeeSpeed_spec term:hasLowerValue ?SqueegeeSpeed_specvalue .
            ?effect term:affects ?product .
            FILTER(xsd:float(?SqueegeeSpeed_obsvalue) < xsd:float(?SqueegeeSpeed_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'SqueegeeSpeedTooLow-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'SqueegeeSpeedTooLow-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "SqueegeeSpeedTooLow-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("SqueegeeSpeedTooLow") AS ?fc_label)
            BIND(IRI(CONCAT(str(assert:), "CA-", "FC-", "SqueegeeSpeedTooLow-", STRAFTER(STR(?product), "#"))) AS ?action)
            BIND("Raise speed into window; balance with pressure/angle" as ?action_label)
            }
        ''',
        'squeegee_angle_fc_query' : '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If SqueegeeAngle < SqueegeeAngle_LSL == SqueegeeAngleTooLow" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?SqueegeeAngle_obs ;
                        term:hasAssessmentInput ?SqueegeeAngle_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:SqueegeeAngleTooLow, term:RootCause ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .

            ?action a term:CorrectiveAction ;
                    rdfs:label ?action_label .
            ?fc term:isCorrectedBy ?action .
            } WHERE {
            ?effect a term:ApertureOverfill .
            ?disposition a term:SqueegeeAngleTooLowDisposition .
            ?SqueegeeAngle_obs a term:SqueegeeAngleObs ;
                                                    term:hasObservedValue ?SqueegeeAngle_obsvalue ;
                                                    iof:isAbout ?SqueegeeAngle_spec ;
                                                    term:observationOf ?product .
                                        ?SqueegeeAngle_spec a term:ParameterSpecification . 
                                    
            ?SqueegeeAngle_spec term:hasLowerValue ?SqueegeeAngle_specvalue .
            ?effect term:affects ?product .
            FILTER(xsd:float(?SqueegeeAngle_obsvalue) < xsd:float(?SqueegeeAngle_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'SqueegeeAngleTooLow-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'SqueegeeAngleTooLow-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "SqueegeeAngleTooLow-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("SqueegeeAngleTooLow") AS ?fc_label)
            BIND(IRI(CONCAT(str(assert:), "CA-", "FC-", "SqueegeeAngleTooLow-", STRAFTER(STR(?product), "#"))) AS ?action)
            BIND("Increase angle toward 60–62°; re-tune pressure/speed instead of flattening" as ?action_label)
            }
        ''',
    },
    'reflow_stage': {
        "non_coalescence_fc_query": '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If PeakReflowTemperature < PeakReflowTemperature_LSL OR TimeAboveLiquidus < TimeAboveLiquidus_LSL == NonCoalescence" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?PeakReflowTemperature_obs ;
                        term:hasAssessmentInput ?PeakReflowTemperature_spec ;
                
            term:hasAssessmentInput ?TimeAboveLiquidus_obs ;
                        term:hasAssessmentInput ?TimeAboveLiquidus_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:NonCoalescence ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .
            } WHERE {
            ?effect a term:OpenCircuit .
            ?disposition a term:NonCoalescenceDisposition .
            ?PeakReflowTemperature_obs a term:PeakReflowTemperatureObs ;
                                                    term:hasObservedValue ?PeakReflowTemperature_obsvalue ;
                                                    iof:isAbout ?PeakReflowTemperature_spec ;
                                                    term:observationOf ?product .
                                        ?PeakReflowTemperature_spec a term:ParameterSpecification . 
                                    

        ?TimeAboveLiquidus_obs a term:TimeAboveLiquidusObs ;
                                                    term:hasObservedValue ?TimeAboveLiquidus_obsvalue ;
                                                    iof:isAbout ?TimeAboveLiquidus_spec ;
                                                    term:observationOf ?product .
                                        ?TimeAboveLiquidus_spec a term:ParameterSpecification . 
                                    
            ?PeakReflowTemperature_spec term:hasLowerValue ?PeakReflowTemperature_specvalue .
        ?TimeAboveLiquidus_spec term:hasLowerValue ?TimeAboveLiquidus_specvalue .
            ?effect term:defectOccursOn ?product .
            FILTER((xsd:float(?PeakReflowTemperature_obsvalue) < xsd:float(?PeakReflowTemperature_specvalue) || xsd:float(?TimeAboveLiquidus_obsvalue) < xsd:float(?TimeAboveLiquidus_specvalue)))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'NonCoalescence-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'NonCoalescence-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "NonCoalescence-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("NonCoalescence") AS ?fc_label)
            }
        ''',
        'peak_reflow_temp_fc_query': '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If PeakReflowTemperature < PeakReflowTemperature_LSL == PeakReflowTemperatureTooLow" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?PeakReflowTemperature_obs ;
                        term:hasAssessmentInput ?PeakReflowTemperature_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:PeakReflowTemperatureTooLow, term:RootCause ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .

            ?action a term:CorrectiveAction ;
                    rdfs:label ?action_label .
            ?fc term:isCorrectedBy ?action .
            } WHERE {
            ?effect a term:NonCoalescence .
            ?disposition a term:PeakReflowTemperatureTooLowDisposition .
            ?PeakReflowTemperature_obs a term:PeakReflowTemperatureObs ;
                                                    term:hasObservedValue ?PeakReflowTemperature_obsvalue ;
                                                    iof:isAbout ?PeakReflowTemperature_spec ;
                                                    term:observationOf ?product .
                                        ?PeakReflowTemperature_spec a term:ParameterSpecification . 
                                    
            ?PeakReflowTemperature_spec term:hasLowerValue ?PeakReflowTemperature_specvalue .
            ?effect term:affects ?product .
            FILTER(xsd:float(?PeakReflowTemperature_obsvalue) < xsd:float(?PeakReflowTemperature_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'PeakReflowTemperatureTooLow-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'PeakReflowTemperatureTooLow-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "PeakReflowTemperatureTooLow-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("PeakReflowTemperatureTooLow") AS ?fc_label)
            BIND(IRI(CONCAT(str(assert:), "CA-", "FC-", "SqueegeeAngleTooLow-", STRAFTER(STR(?product), "#"))) AS ?action)
            BIND("Raise peak within vendor band" as ?action_label)
            }
        ''',
        'time_above_liquidus_fc_query': '''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX bfo: <http://purl.obolibrary.org/obo/>
            PREFIX prov: <http://www.w3.org/ns/prov#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            CONSTRUCT { 
            ?coa a term:ConformanceAssessment ;
                term:triggeredByRule "If TimeAboveLiquidus < TimeAboveLiquidus_LSL == TimeAboveLiquidusTooLow" ;
                term:realizationOf ?disposition ;
                term:hasAssessmentInput ?TimeAboveLiquidus_obs ;
                        term:hasAssessmentInput ?TimeAboveLiquidus_spec ;
                
                rdfs:label ?coa_label .
            ?fc a term:TimeAboveLiquidusTooLow, term:RootCause ;
                prov:wasGeneratedBy ?coa ;
                term:affects ?product ;
                rdfs:label ?fc_label .
            ?effect term:directlyCausallyInfluencedBy ?fc .

            ?action a term:CorrectiveAction ;
                    rdfs:label ?action_label .
            ?fc term:isCorrectedBy ?action .
            } WHERE {
            ?effect a term:NonCoalescence .
            ?disposition a term:TimeAboveLiquidusTooLowDisposition .
            ?TimeAboveLiquidus_obs a term:TimeAboveLiquidusObs ;
                                                    term:hasObservedValue ?TimeAboveLiquidus_obsvalue ;
                                                    iof:isAbout ?TimeAboveLiquidus_spec ;
                                                    term:observationOf ?product .
                                        ?TimeAboveLiquidus_spec a term:ParameterSpecification . 
                                    
            ?TimeAboveLiquidus_spec term:hasLowerValue ?TimeAboveLiquidus_specvalue .
            ?effect term:affects ?product .
            FILTER(xsd:float(?TimeAboveLiquidus_obsvalue) < xsd:float(?TimeAboveLiquidus_specvalue))
            BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'TimeAboveLiquidusTooLow-rule-1')) AS ?coa)
            BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", 'TimeAboveLiquidusTooLow-rule-1') AS ?coa_label)
            BIND(IRI(CONCAT(str(assert:), "FC-", "TimeAboveLiquidusTooLow-", STRAFTER(STR(?product), "#"))) AS ?fc)
            BIND(CONCAT("TimeAboveLiquidusTooLow") AS ?fc_label)
            BIND(IRI(CONCAT(str(assert:), "CA-", "FC-", "SqueegeeAngleTooLow-", STRAFTER(STR(?product), "#"))) AS ?action)
            BIND("Increase TAL per paste spec" as ?action_label)
            }
        '''
    }
}

