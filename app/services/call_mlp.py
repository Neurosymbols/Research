
import requests

MLP_API_URL = "http://localhost:8000/predict"
TIMEOUT = 5  # seconds


def call_mlp_api(pcb_features: dict) -> dict:
    """
    Calls the MLP inference API and returns the JSON response.
    Raises RuntimeError on failure.
    """

    try:
        response = requests.post(
            MLP_API_URL,
            json=pcb_features,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"MLP API error {response.status_code}: {response.text}"
            )

        return response.json()

    except requests.exceptions.Timeout:
        raise RuntimeError("MLP API timeout")

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"MLP API request failed: {e}")

def extract_for_kg(mlp_response: dict):
    """
    Extracts ONLY the fields required for GraphDB insertion
    from a raw MLP response.
    """

    # -----------------------------
    # DEFECT
    # -----------------------------
    defect_raw = mlp_response.get("defect", {})

    defect = {
        "name": defect_raw.get("class"),
        "probability": float(defect_raw.get("confidence", 0.0)),
        "description": defect_raw.get("description", ""),
        "source": defect_raw.get("source", "MLP")
    }

    # -----------------------------
    # PRINT STAGE MECHANISM (derived from class)
    # -----------------------------
    mech_raw = mlp_response.get("printing_mechanism", {})
    # Treat "No Mechanism" as absence
    print_mechanism = {
        "name": mech_raw.get("class"),
        "probability": float(mech_raw.get("confidence", 0.0)),
        "description": mech_raw.get(
            "description",
            f"{mech_raw.get('class')} detected"
        ),
        "source": mech_raw.get("source", "MLP")
    }
    
    # -----------------------------
    # REFLOW STAGE MECHANISM (derived from class)
    # -----------------------------
    mech_raw = mlp_response.get("reflow_mechanism", {})
    # Treat "No Mechanism" as absence
    reflow_mechanism = {
        "name": mech_raw.get("class"),
        "probability": float(mech_raw.get("confidence", 0.0)),
        "description": mech_raw.get(
            "description",
            f"{mech_raw.get('class')} detected"
        ),
        "source": mech_raw.get("source", "MLP")
    }

    # -----------------------------
    # VIOLATIONS (derived from parameters)
    # -----------------------------
    violations = []

    parameters = mlp_response.get("parameters", {})
    param_map = {
        "paste_volume": "paste_volume_per_aperture"
    }
    for param_name, param_data in parameters.items():
        pn = param_map.get(param_name, param_name)
        risk_score =  param_data.get("risk_score", 0.0)
        risk_score_threshold = 0.60
        if risk_score >= risk_score_threshold:
            violations.append({
                "parameter": pn,
                "direction": param_data.get("direction"),
                "probability": float(param_data.get("risk_score", 0.0)),
                "source": "MLP"
            })

    return {
        "defect": defect,
        "print_mechanism": print_mechanism,
        "reflow_mechanism": reflow_mechanism,
        "violations": violations
    }
