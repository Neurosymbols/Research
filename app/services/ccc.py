import pandas as pd
import json
import requests
from datetime import datetime, timezone

from .call_mlp import extract_for_kg, call_mlp_api
from .utils import perform_sparql_update, create_classname_syntax
from app.models import *
from app.config.data_paths import resources

def build_mlp_payload(row: dict, default_temp: float = 25.0) -> dict:
    """
    Converts a synthetic CSV row dict into an MLP API payload.
    """

    return {
        "pcb_id": row["PCB_ID"],
        "paste_volume": float(row["Paste volume per aperture"]),
        "stencil_thickness": float(row["Stencil thickness"]),  # mm → µm
        "paste_viscosity": float(row["Paste viscosity"]),
        "ambient_rh": float(row["Ambient RH"]),
        "ambient_temperature": float(row["Ambient temperature"]),
        "peak_reflow_temperature": float(row["Peak reflow temperature"]),
        "time_above_liquidus": float(row["Time above liquidus"]),
    }
def get_ml_model_iri(model_metadata: dict) -> str:
    model_type = create_classname_syntax(model_metadata["type"])
    version = model_metadata["version"]
    return f"ind:MLModel-{model_type}-v{version}"

PREFIXES = """
PREFIX base: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
PREFIX ind: <https://neurosymbols.ai/data/causal-assertions.owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX prov: <http://www.w3.org/ns/prov#>
"""

# ------------------------------------------------------------------
# Upsert ML Model Object
# ------------------------------------------------------------------

def upsert_ml_model(model_metadata: dict):
    model_iri = get_ml_model_iri(model_metadata)

    sparql = PREFIXES + f"""
    INSERT {{
        {model_iri}
            rdf:type base:PredictiveModel ;
            base:modelType "{model_metadata['type']}" ;
            base:modelVersion "{model_metadata['version']}"^^xsd:integer ;
            base:totalFeatures "{model_metadata['total_features']}"^^xsd:integer ;
            base:defectClasses "{model_metadata['defect_classes']}"^^xsd:integer ;
            base:mechanismClasses "{model_metadata['mechanism_classes']}"^^xsd:integer ;
            base:rawFeatures "{model_metadata['raw_features']}"^^xsd:integer .
    }}
    WHERE {{
        FILTER NOT EXISTS {{
            {model_iri} rdf:type base:PredictiveModel .
        }}
    }}
    """
    perform_sparql_update(sparql)
    return model_iri

# ------------------------------------------------------------------
# Update EXISTING defect individual
# ------------------------------------------------------------------

def update_defect(pcb_id, defect):
    if defect['name'] == "No Defect":
        return
    class_name = create_classname_syntax(defect['name'])
    defect_iri = f"ind:{class_name}_{pcb_id}"
    defect_label = f"{class_name}_{pcb_id}"
    print(defect_iri)
    now = datetime.now(timezone.utc).isoformat()

    sparql = PREFIXES + f"""
        INSERT {{
            {defect_iri} rdf:type base:{class_name} .
        }}
        WHERE {{
            FILTER NOT EXISTS {{
                {defect_iri} rdf:type base:{class_name} .
            }}
        }};

        DELETE {{
            {defect_iri} base:hasProbability ?c ;
                        base:hasSource ?s ;
                        base:hasDescription ?d ;
                        base:lastUpdated ?t .
        }}
        INSERT {{
            {defect_iri}
                base:hasProbability {defect['probability']} ;
                base:hasSource "MLP" ;
                base:hasDescription "{defect['description']}" ;
                base:defectOccursOn ind:{pcb_id} ;
                base:lastUpdated "{now}"^^xsd:dateTime ;
                rdfs:label "{defect_label}" .
        }}
        WHERE {{
            OPTIONAL {{ {defect_iri} base:hasProbability ?c }}
            OPTIONAL {{ {defect_iri} base:hasSource ?s }}
            OPTIONAL {{ {defect_iri} base:hasDescription ?d }}
            OPTIONAL {{ {defect_iri} base:lastUpdated ?t }}
        }}
    """
    perform_sparql_update(sparql)

# ------------------------------------------------------------------
# 5. Create mechanism
# ------------------------------------------------------------------

def create_mechanism(pcb_id, mech):
    if mech is None:
        return
    class_name = create_classname_syntax(mech["name"])
    mech_iri = f"ind:{class_name}_{pcb_id}"
    now = datetime.now(timezone.utc).isoformat()

    sparql = PREFIXES + f"""
        INSERT DATA {{
            {mech_iri}
                rdf:type base:{class_name} ;
                rdfs:label "{class_name}" ;
                base:hasProbability {mech['probability']} ;
                base:hasSource "{mech['source']}" ;
                base:hasDescription "{mech['description']}" ;
                base:affects ind:{pcb_id} ;
                base:createdAt "{now}"^^xsd:dateTime .
        }}
    """

    perform_sparql_update(sparql)
    return mech_iri

# ------------------------------------------------------------------
# 6. Create violations
# ------------------------------------------------------------------
def create_violation(pcb_id, v, ml_model_iri):
    parameter_spec_map = {}
    with open(resources.specs_json) as f:
        specs_dict = json.load(f)
        parameter_spec_map = {create_classname_syntax(k):v['id'] for k, v in specs_dict.items()}

    class_name = create_classname_syntax(f"{v['direction'].capitalize()} {v['parameter']}")

    viol_iri = f"ind:{class_name}_{pcb_id}"
    assessment_iri = f"ind:COA-{pcb_id}-{class_name}"
    param_obs_ind = f"ind:{create_classname_syntax(v['parameter'])}_{pcb_id}_Obs"
    param_spec_ind = f"ind:{parameter_spec_map[create_classname_syntax(v['parameter'])]}-spec"

    now = datetime.now(timezone.utc).isoformat()

    sparql_assessment = PREFIXES + f"""
    DELETE {{
        {assessment_iri}
            base:hasProbability ?p ;
            base:hasSource ?s ;
            base:createdAt ?t ;
            base:performedOn ?pcb ;
            base:hasAssessmentInput ?in ;
            prov:used ?m .
    }}
    INSERT {{
        {assessment_iri}
            rdf:type base:ConformanceAssessment ;
            base:hasProbability {v['probability']} ;
            base:hasSource "{v['source']}" ;
            base:createdAt "{now}"^^xsd:dateTime ;
            base:performedOn ind:{pcb_id} ;
            base:hasAssessmentInput {param_obs_ind} ;
            base:hasAssessmentInput {param_spec_ind} ;
            prov:used {ml_model_iri} .
    }}
    WHERE {{
        OPTIONAL {{ {assessment_iri} base:hasProbability ?p }}
        OPTIONAL {{ {assessment_iri} base:hasSource ?s }}
        OPTIONAL {{ {assessment_iri} base:createdAt ?t }}
        OPTIONAL {{ {assessment_iri} base:performedOn ?pcb }}
        OPTIONAL {{ {assessment_iri} base:hasAssessmentInput ?in }}
        OPTIONAL {{ {assessment_iri} prov:used ?m }}
    }}
    """
    perform_sparql_update(sparql_assessment)

    sparql_violation = PREFIXES + f"""
    DELETE {{
        {viol_iri}
            rdf:type ?type ;
            rdfs:label ?lbl ;
            base:affects ?pcb ;
            prov:wasGeneratedBy ?gen .
    }}
    INSERT {{
        {viol_iri}
            rdf:type base:{class_name} ;
            rdf:type base:Effect ;
            rdfs:label "{class_name}" ;
            base:affects ind:{pcb_id} ;
            prov:wasGeneratedBy {assessment_iri} .
    }}
    WHERE {{
        OPTIONAL {{ {viol_iri} rdf:type ?type }}
        OPTIONAL {{ {viol_iri} rdfs:label ?lbl }}
        OPTIONAL {{ {viol_iri} base:affects ?pcb }}
        OPTIONAL {{ {viol_iri} prov:wasGeneratedBy ?gen }}
    }}
    """
    perform_sparql_update(sparql_violation)


# ------------------------------------------------------------------
# 7. Main loop
# ------------------------------------------------------------------
def perform_conformance_assessment_mlp(ctx: PipelineContext):
    df = ctx.runtime.factory_data
    i = 0
    for _, row in df.iterrows():
        pcb_id = row["PCB_ID"]
        mlp_payload = build_mlp_payload(dict(row))
        mlp_result_api = call_mlp_api(mlp_payload)
        ml_model_iri = upsert_ml_model(mlp_result_api["model_metadata"])
        kg_ready_resp = extract_for_kg(mlp_result_api, ctx)

        # 1. Update defect (existing individual)
        update_defect(pcb_id, kg_ready_resp["defect"])

        # 2. Create mechanisms
        print_mech = kg_ready_resp["print_mechanism"]
        print_mech_iri = create_mechanism(pcb_id, print_mech)

        reflow_mech = kg_ready_resp["reflow_mechanism"]
        reflow_mech_iri = create_mechanism(pcb_id, reflow_mech)

        # 3. Create violations
        for v in kg_ready_resp["violations"]:
            create_violation(pcb_id, v, ml_model_iri)
        i += 1
        print(i)
        if(i == 1000):
            break
