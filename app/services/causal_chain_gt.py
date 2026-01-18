import pandas as pd
import json


from app.services.utils import create_classname_syntax

output_path = "./app/data/output/epoch3-7"
input_path = "./app/data/input/epoch3-7"

# --- Spec + failure cause mapping ---
cause_mapping = {
    "HighPasteVolumePerAperture": "paste volume per aperture",
    "LowPasteVolumePerAperture": "paste volume per aperture",
    "LowAreaRatio": "aperture area ratio",
    "HighBeadSizeOfSolderPaste": "paste roll bead size",
    "HighStencilThickness": "stencil thickness",
    "LowStencilThickness": "stencil thickness",
    "HighSqueegeeSpeed": "squeegee speed",
    "LowSqueegeeSpeed": "squeegee speed",
    "HighSqueegeeAngle": "squeegee angle",
    "HighSqueegeePressure": "squeegee pressure",
    "LowSqueegeePressure": "squeegee pressure",
    "ResidualPasteVolume": "residual paste",
    "LowPasteViscosity": "paste viscosity",
    "HighPasteViscosity": "paste viscosity",
    "HighAmbientRh": "ambient rh",
    "LowAmbientRh": "ambient rh",
    "HighPeakReflowTemperature": "peak reflow temperature",
    "LowPeakReflowTemperature": "peak reflow temperature",
    "HighTimeAboveLiquidus": "time above liquidus",
    "LowTimeAboveLiquidus": "time above liquidus",
    "LowMetalLoad": "metal load"
}

mechanism_failures = [
    "HighPasteVolumePerAperture",
    "LowPasteVolumePerAperture"
]

ishikawa_graph = {
  "SolderBridging": {
    "caused_by": [
      "HighPasteVolumePerAperture",
      "ExcessReflowSpreading",
      "ApertureOverfill"
    ],
    "type": "defect"
  },
  "HighPasteVolumePerAperture": {
    "caused_by": [
      "ApertureOverfill",
      "UndersideSmear",
      "PostPrintSpread"
    ]
  },
  "ExcessReflowSpreading": {
    "caused_by": [
      "HighPeakReflowTemperature",
      "HighTimeAboveLiquidus"
    ],
  },
  "ApertureOverfill": {
    "caused_by": [
      "LowAreaRatio",
      "HighBeadSizeOfSolderPaste",
      "HighStencilThickness",
      "LowSqueegeeAngle",
      "LowSqueegeeSpeed",
      "LowPasteViscosity",
      "HighAmbientRh",
      "HighAmbientTemperature"
    ]
  },
  "UndersideSmear": {
    "caused_by": [
      "HighSqueegeePressure",
      "ResidualPasteVolume"
    ]
  },
  "PostPrintSpread": {
    "caused_by": [
      "LowPasteViscosity",
      "HighHumidity",
      "LowMetalLoad"
    ]
  },
  "OpenCircuit": {
    "caused_by": [
      "NonCoalescence",
      "LowPasteVolumePerAperture",
      "PoorPasteTransfer"
    ],
    "type": "defect"
  },
  "NonCoalescence": {
    "caused_by": [
      "TimeAboveLiquidus",
      "PeakReflowTemperature"
    ]
  },
  "LowPasteVolumePerAperture": {
    "caused_by": [
      "PoorPasteTransfer"
    ]
  },
  "PoorPasteTransfer": {
    "caused_by": [
      "LowStencilThickness",
      "LowAmbientRh",
      "HighPasteViscosity",
      "HighSqueegeeSpeed",
      "LowSqueegeePressure",
      "LowAmbientTemperature"
    ]
  }
}

def create_gt_causal_chains(
        effect, 
        row_mech_causes, 
        row_root_causes,
        chain = []
):
    defects = [k for k, v in ishikawa_graph.items() if v.get("type", "") == "defect"]
    if effect.split("_")[0] in defects:
        defect_name = effect.split("_")[0]
        for cause in ishikawa_graph[defect_name]['caused_by']:
            if cause in row_mech_causes:
                chain.append([effect, cause])
                return create_gt_causal_chains(
                    cause,
                    [r for r in row_mech_causes if r != cause],
                    row_root_causes,
                    chain
                )
            elif cause in row_root_causes:
                chain.append([effect, cause])
        return chain
            
    elif row_mech_causes:
        for cause in ishikawa_graph[effect]['caused_by']:
            if cause in row_mech_causes:
                chain.append([effect, cause])
                return create_gt_causal_chains(
                    cause,
                    [r for r in row_mech_causes if r != cause],
                    row_root_causes,
                    chain
                )
            elif cause in row_root_causes:
                chain.append([effect, cause])
        return chain
    #base condition
    else:
        for cause in ishikawa_graph[effect]['caused_by']:
            if cause in row_root_causes:
                chain.append([effect, cause])
        return chain

def generate_ground_truth(reuse=False):
    def is_empty(x):
        return pd.isna(x) or str(x).strip() == "" or str(x).strip() == "No Defect"

    def is_not_empty(x):
        return not is_empty(x)

    df_ppf = None
    if reuse:
        df_ppf = pd.read_csv(
            f"{input_path}/synthetic_data_factory_5.csv", 
            index_col=0
        )
    
    df_ppf.columns = df_ppf.columns.str.strip()
    mask = (
        df_ppf["Defect"].apply(is_not_empty) |
        (
            df_ppf["Defect"].apply(is_empty) &
            (
                df_ppf["mech causes"].apply(is_not_empty) |
                df_ppf["root causes"].apply(is_not_empty)
            )
        )
    )
    df_ppf = df_ppf[mask]
    print(len(df_ppf))

    # --- Apply to DataFrame ---
    root_cause_list = []
    mechanism_failure_list = []
    defect_list = []
    pcb_ids = []
    pcb_chains = {}

    df_ppf['PCB_ID'] = None
    for index, row in df_ppf.iterrows():
        pcb_ids.append(f"PCB{index+1}")
        df_ppf.loc[index, 'PCB_ID'] = f"PCB{index+1}"
        row_root_causes = []
        row_mech_causes = []
        defects = []
        if not pd.isna(row['root causes']):
            row_root_causes = [create_classname_syntax(r.strip().lower()) for r in row['root causes'].split(";")]
        if not pd.isna(row['mech causes']):
            row_mech_causes = [create_classname_syntax(r.strip().lower()) for r in row['mech causes'].split(";")]
        if not pd.isna(row['Defect']):
            defects = [f"{create_classname_syntax(r.strip().lower())}_PCB{index+1}" for r in row['Defect'].split(";") if r.strip().lower() != "no defect"]
        if len(defects) > 0 or len(row_root_causes) > 0:
            chain = []
            if len(defects) > 0:
                for d in defects:
                    chain_a = create_gt_causal_chains(
                        d, row_mech_causes, row_root_causes, []
                    )
                    chain.extend(chain_a)
            else:
                if len(row_mech_causes) > 0:
                    row_mech_causes_dup = [v for v in row_mech_causes]
                    chain_a = create_gt_causal_chains(
                            row_mech_causes_dup.pop(0), row_mech_causes, row_root_causes, []
                        )
                    chain.extend(chain_a)
                # else:
                #     chain.append(row_root_causes)
            pcb_chains[f"PCB{index+1}"] = chain

        root_cause_list.append(", ".join(list(set(row_root_causes))))
        mechanism_failure_list.append(", ".join(list(set(row_mech_causes))))
        defect_list.append(", ".join(list(set(defects))))

    cols = ['PCB_ID'] + [c for c in df_ppf.columns if c != 'PCB_ID']
    df_ppf = df_ppf[cols]
    df_ppf.to_csv(f"{input_path}/synthetic_data_factory_5.csv", index=False)
    with open(f"{input_path}/test_chains_3.json", "w") as f:
        json.dump(pcb_chains, f, indent=1)

generate_ground_truth(reuse=True)

