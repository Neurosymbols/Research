import pandas as pd
import requests
from datetime import datetime, timezone

from .call_mlp import extract_for_kg, call_mlp_api
from .utils import perform_sparql_update, create_classname_syntax
from .causal_chains import create_causal_chain, infere_root_causes

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
        "ambient_temperature": float(row["Ambient temperature"])
    }


PREFIXES = """
PREFIX base: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
PREFIX ind: <https://neurosymbols.ai/data/causal-assertions.owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
# ------------------------------------------------------------------
# 1. Load PCB data
# ------------------------------------------------------------------

df = pd.read_csv("./app/data/input/epoch3-7/synthetic_data_factory_5.csv")

# ------------------------------------------------------------------
# 4. Update EXISTING defect individual
# ------------------------------------------------------------------

def update_defect(pcb_id, defect):
    if defect['class'] == "No Defect":
        return
    class_name = create_classname_syntax(defect['class'])
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
                base:isPresent true ;
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
def create_violation(pcb_id, v):
    class_name = create_classname_syntax(f"{v['direction'].capitalize()} {v['parameter']}")
    viol_iri = f"ind:{class_name}_{pcb_id}"
    now = datetime.now(timezone.utc).isoformat()
    sparql = PREFIXES + f"""
        INSERT DATA {{
        {viol_iri}
            rdf:type base:{class_name} ;
            rdfs:label "{class_name}" ;
            base:hasProbability {v['probability']} ;
            base:hasDescription "{v['warning']}" ;
            base:hasSource "{v['source']}" ;
            base:affects ind:{pcb_id} ;
            base:createdAt "{now}"^^xsd:dateTime .
        }}
    """
    perform_sparql_update(sparql)


# ------------------------------------------------------------------
# 7. Main loop
# ------------------------------------------------------------------

i = 0
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
df = df[mask]
for _, row in df.iterrows():
    pcb_id = row["PCB_ID"]
    mlp_payload = build_mlp_payload(dict(row))
    mlp_result_api = call_mlp_api(mlp_payload)
    kg_ready_resp = extract_for_kg(mlp_result_api)

    # 1. Update defect (existing individual)
    update_defect(pcb_id, kg_ready_resp["defect"])

    # 2. Create mechanisms
    mech = kg_ready_resp["mechanism"]
    mech_iri = create_mechanism(pcb_id, mech)

    # 3. Create violations
    for v in kg_ready_resp["violations"]:
        create_violation(pcb_id, v)
    i += 1
    print(i)
    if(i == 1000):
        break

create_causal_chain(verb="INSERT")
infere_root_causes(verb="INSERT")
print("✅ GraphDB update completed successfully")