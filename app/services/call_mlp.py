
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
        "class": defect_raw.get("class"),
        "probability": float(defect_raw.get("confidence", 0.0)),
        "description": defect_raw.get("description", ""),
        "source": defect_raw.get("source", "MLP")
    }

    # -----------------------------
    # MECHANISM (derived from class)
    # -----------------------------
    mechanism = None
    mech_raw = mlp_response.get("mechanism", {})

    mech_class = mech_raw.get("class")
    mech_confidence = float(mech_raw.get("confidence", 0.0))

    # Treat "No Mechanism" as absence
    if mech_class and mech_class.lower() not in {"no mechanism", "none"}:
        mechanism = {
            "name": mech_class,
            "probability": mech_confidence,
            "description": mech_raw.get(
                "description",
                f"{mech_class} detected"
            ),
            "present": True,
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
        if param_data.get("direction") == "Safe":
            continue  # skip non-risk parameters

        violations.append({
            "parameter": pn,
            "direction": param_data.get("direction"),
            "probability": float(param_data.get("risk_score", 0.0)),
            "warning": param_data.get("status"),
            "source": "MLP"
        })

    return {
        "defect": defect,
        "mechanism": mechanism,
        "violations": violations
    }
