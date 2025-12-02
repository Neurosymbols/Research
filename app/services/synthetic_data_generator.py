import random
import numpy as np
import pandas as pd
import scipy.stats as st
import json
import re

from asteval import Interpreter

from app.services.utils import create_classname_syntax

aeval = Interpreter()


output_path = "./app/data/output/epoch3-7"
input_path = "./app/data/input/epoch3-7"

#def_mod
#aim: tighter sigma, recall/precision around 90%
#sigma decreases, def_mod increases, FN decrease
#decrease one off chains -> 
process_parameters = {
    # monte carlo simluation, #discrete event simulation
    "Stencil thickness": {
        "NV": 0.100,
        "tolerance": 0.005,
        "USL": 0.105,
        "LSL": 0.095,
        "sigma": 0.00167
    #  σ = tol/x → 0.005 / 3 = 0.00167 (1.67% of NV) ✅ realistic (tight dimensional control)
    },
    "Paste volume per aperture": {
        "NV": 0.04,
        "tolerance": 0.004,
        "USL": 0.044,
        "LSL": 0.036,
        "sigma": 0.00133
    #  σ = tol/3 → 0.004 / 3 = 0.00133 (3.3% of NV) ✅ realistic (printing variation)
    },
    "Paste roll bead size": {
        "NV": 4,
        "tolerance": 0.4,
        "USL": 4.4,
        "LSL": 3.6,
        "sigma": 0.1133
    #  σ = tol/3.53 → 0.4 / 3 = 0.1133 (3.3% of NV) ✅ realistic
    #  σ = tol/4.5 → 0.4 / 4.5 = 0.08889 (3.3% of NV) ✅ realistic
    },
    "Residual paste": {
        "NV": 5,
        "tolerance": 0.5,
        "USL": 5.5,
        "LSL": 4.5,
        "sigma": 0.16667
    #  σ = tol/3 → 0.5 / 3 = 0.16667 (3.3% of NV) ✅ acceptable (measurement variation)
    },
    "Squeegee pressure": {
        "NV": 0.30,
        "tolerance": 0.03,
        "USL": 0.33,
        "LSL": 0.27,
        "sigma": 0.01000
    # σ = tol/3 → 0.03 / 3 = 0.010 (3.3% of NV) ✅ realistic (machine repeatability)
    },
    "Squeegee speed": {
        "NV": 70,
        "tolerance": 14,
        "USL": 84,
        "LSL": 56,
        "sigma": 4.2
    # // adjusted σ = (tol/3.33) ≈ 2.8 (4% of NV) ⚙️ tightened from 4.67 (6.7%) for realism
    },
    "Squeegee angle": {
        "NV": 60,
        "tolerance": 5,
        "USL": 65,
        "LSL": 55,
        "sigma": 1.67
    # // σ = tol/3 → 5 / 3 = 1.67 (2.8% of NV) ✅ realistic (angular control)
    },
    "Aperture area ratio": {
        "NV": 0.66,
        "tolerance": None,
        "USL": None,
        "LSL": 0.66,  # since only minimum is specified
        "target_defect_rate": [0.001, 0.002], #fine tune range here
        "sigma_pct": 0.03
    },
    "Paste viscosity": {
        "NV": 200,
        "tolerance": 50,
        "USL": 250,
        "LSL": 150,
        "sigma": 10.00
    # // adjusted σ ≈ 10 (≈ tol/5) → 5% of NV ⚙️ lowered from 16.7 for realistic paste batch spread
    },
    "Peak reflow temperature": {
        "NV": 255,
        "tolerance": 5,
        "USL": 260,
        "LSL": 250,
        "sigma": 1.67
    # // σ = tol/3 → 5 / 3 = 1.67 (0.65% of NV) ✅ realistic for stable ovens
    },
    "Ambient RH": {
        "NV": 40,
        "tolerance": 10,
        "USL": 50,
        "LSL": 30,
        "sigma": 2.00
    # // adjusted σ = tol/5 = 2.0 (5% of NV) ⚙️ lowered from 3.33 for humidity-controlled line
    },
    "metal load": {
        "NV": 80,
        "tolerance": 10,
        "USL": 90,
        "LSL": 70,
        "sigma": 3.33
    # // σ = tol/3 → 10 / 3 = 3.33 (4.2% of NV) ✅ realistic for alloy composition
    # // σ = tol/5 → 10 / 5 = 2 (4.2% of NV) ✅ realistic for alloy composition
    },
    "Time Above Liquidus": {
        "NV": 60,
        "tolerance": 15,
        "USL": 75,
        "LSL": 45,
        "sigma": 2.50
    # // adjusted σ ≈ tol/6 → 2.5 (4.2% of NV) ⚙️ lowered from 5.0 for realistic reflow profile control
    }
}
# --- Spec + failure cause mapping ---
cause_mapping = {
    "ExcessPasteVolumePerAperture": "paste volume per aperture",
    "InsufficientPasteVolumePerAperture": "paste volume per aperture",
    "LowAreaRatio": "aperture area ratio",
    "LargeBeadSizeOfSolderPaste": "paste roll bead size",
    "StencilThicknessTooHigh": "stencil thickness",
    "SqueegeeSpeedTooLow": "squeegee speed",
    "SqueegeeSpeedTooHigh": "squeegee speed",
    "SqueegeeAngleTooLow": "squeegee angle",
    "SqueegeePressureTooHigh": "squeegee pressure",
    "SqueegeePressureTooLow": "squeegee pressure",
    "HighResidualPasteVolume": "residual paste",
    "LowPasteViscosity": "paste viscosity",
    "HighHumidity": "ambient rh",
    "PeakReflowTemperatureTooHigh": "peak reflow temperature",
    "PeakReflowTemperatureTooLow": "peak reflow temperature",
    "TimeAboveLiquidusTooHigh": "time above liquidus",
    "TimeAboveLiquidusTooLow": "time above liquidus",
    "LowMetalLoad": "metal load"
}

mechanism_failures = [
    "ExcessPasteVolumePerAperture",
    "InsufficientPasteVolumePerAperture"
]

ishikawa_graph = {
  "SolderBridging": {
    "caused_by": [
      "ExcessPasteVolumePerAperture",
      "ExcessReflowSpreading"
    ],
    "type": "defect"
  },
  "ExcessPasteVolumePerAperture": {
    "caused_by": [
      "ApertureOverfill",
      "UndersideSmear",
      "PostPrintSpread"
    ],
    "rules": [
        "If PasteVolumePerAperture > PasteVolumePerAperture_USL == ExcessPasteVolumePerAperture"
    ]
  },
  "ExcessReflowSpreading": {
    "caused_by": [
      "PeakReflowTemperatureTooHigh",
      "TimeAboveLiquidusTooHigh"
    ],
    "rules":[
        "If PeakReflowTemperature > PeakReflowTemperature_USL OR TimeAboveLiquidus > TimeAboveLiquidus_USL == ExcessReflowSpreading"
    ]
  },
  "ApertureOverfill": {
    "caused_by": [
      "LowAreaRatio",
      "LargeBeadSizeOfSolderPaste",
      "StencilThicknessTooHigh",
      "SqueegeeAngleTooLow",
      "SqueegeeSpeedTooLow"
    ],
    "rules":[
        "If PasteRollBeadSize > PasteRollBeadSize_USL == ApertureOverfill",
        "If ApertureAreaRatio < ApertureAreaRatio_LSL OR StencilThickness > StencilThickness_USL == ApertureOverfill",
        "If SqueegeeAngle < SqueegeeAngle_LSL AND (SqueegeeSpeed < SqueegeeSpeed_LSL OR SqueegeePressure > SqueegeePressure_USL) == ApertureOverfill"
    ]
  },
  "UndersideSmear": {
    "caused_by": [
      "SqueegeePressureTooHigh",
      "HighResidualPasteVolume"
    ],
    "rules":[
        "If SqueegeePressure > SqueegeePressure_USL OR ResidualPaste > ResidualPaste_USL == UndersideSmear"
    ]
  },
  "PostPrintSpread": {
    "caused_by": [
      "LowPasteViscosity",
      "HighHumidity",
      "LowMetalLoad"
    ],
    "rules":[
        "If PasteViscosity < PasteViscosity_LSL OR AmbientRh > AmbientRh_USL == PostPrintSpread",
        "If MetalLoad < MetalLoad_LSL == PostPrintSpread"
    ]
  },
  "OpenCircuit": {
    "caused_by": [
      "NonCoalescence",
      "InsufficientPasteVolumePerAperture"
    ],
    "type": "defect"
  },
  "NonCoalescence": {
    "caused_by": [
      "TimeAboveLiquidusTooLow",
      "PeakReflowTemperatureTooLow"
    ],
    "rules":[
        "If PeakReflowTemperature < PeakReflowTemperature_LSL OR TimeAboveLiquidus < TimeAboveLiquidus_LSL == NonCoalescence"
    ]
  },
  "InsufficientPasteVolumePerAperture": {
    "caused_by": [
      "PoorPasteTransfer"
    ],
    "rules":[
        "If PasteVolumePerAperture < PasteVolumePerAperture_LSL == InsufficientPasteVolumePerAperture"
    ]
  },
  "PoorPasteTransfer": {
    "caused_by": [
      "SqueegeeSpeedTooHigh",
      "SqueegeePressureTooLow"
    ],
    "rules":[
        "If SqueegeeSpeed > SqueegeeSpeed_USL OR SqueegeePressure < SqueegeePressure_LSL == PoorPasteTransfer"
    ]
  }
}

# --- Define helper to get cause names ---
def get_causes(
        param, 
        value, 
        lower, 
        upper, 
        index,
        spec_data
    ):
    causes = []
    mechanism_causes = []

    # High-side violation
    if upper and value > upper:
        spec_data[param]['upper'] += 1
        matching_causes = [k for k, v in cause_mapping.items() if v == param and ("High" in k or "Excess" in k or "Large" in k)]
        cause_name = matching_causes[0] if matching_causes else None
        if cause_name:
            if cause_name in mechanism_failures:
                mechanism_causes.append(cause_name)
            else:
                causes.append(cause_name)

    # Low-side violation
    if lower and value < lower:
        spec_data[param]['lower'] += 1
        matching_causes = [k for k, v in cause_mapping.items() if v == param and ("Low" in k or "Insufficient" in k)]
        cause_name = matching_causes[0] if matching_causes else None
        if cause_name:
            if cause_name in mechanism_failures:
                mechanism_causes.append(cause_name)
            else:
                causes.append(cause_name)
    return causes, mechanism_causes

#take below fact with grain of salt because observations say otherwise because my mean is centered
# High σ% ⇒ more natural failures / wider tails. For parameters where % of NV is large (≥ ~5–8%), you’ll see more out-of-spec samples and more sensitivity in downstream defect mapping.
# Low σ% ⇒ very few defects from noise. Parameters like reflow temp (0.65%) will rarely produce out-of-spec events unless the mean shifts.

# Function to generate a n samples using PPF for each param
def generate_samples_ppf(param_info, n=1000):
    NV = param_info["NV"]
    sigma = param_info["sigma"]

    # Generate n uniform(0,1) random numbers
    normals = np.random.rand(n)
    # Apply vectorized PPF
    samples = st.norm.ppf(normals, loc=NV, scale=sigma)

    # Return regular python list
    return samples.tolist()

def sigma_percent():
    data = []
    for name, info in process_parameters.items():
        NV = info["NV"]
        tol = info["tolerance"]
        #Is 1σ large or small? Depends on the size of σ relative to NV or tolerance
        if tol:
            sigma = round(tol / 3, 5)
            sigma_percent = (sigma/NV)*100
            data.append({
                "name": name,
                "NV": NV,
                "sigma": sigma,
                "sigma pct of NV": round(sigma_percent,5)
            })
    with open(f"{output_path}/sigma_percent_data.json", "w") as f:
        json.dump(data, f, indent = 2)

def calculate_mu_and_sigma_for_on_sided_specs(param_info):
    assert 'target_defect_rate' in param_info, "target_defect_rate is missing"
    assert 'sigma_pct' in param_info, "sigma pct of NV is missing"
    assert param_info['NV'] is not None, "nominal value absent"
    # Pick random target defect rate from given range for the parameter
    p_target = random.uniform(
        param_info['target_defect_rate'][0], 
        param_info['target_defect_rate'][1]
    )
    sigma = param_info['sigma_pct'] * param_info['NV']
    # Find mean μ such that P(X < LSL) = p_target
    z_p = st.norm.ppf(p_target)  # z-score for that percentile (negative)
    assert z_p < 0, "z-score is positive, please check"
    mu = param_info['LSL'] - z_p * sigma  # shift mean upward
    param_info['NV'] = mu
    param_info['sigma'] = sigma

def data_factory(size=1000):
    # Generate "size" number of samples for each parameter
    for k, v in process_parameters.items():
        if not v['tolerance']:
            calculate_mu_and_sigma_for_on_sided_specs(v)
    samples_ppf = {
        name: generate_samples_ppf(info, size)
        for name, info in process_parameters.items()
    }
    # Create a Pandas DataFrame
    df_ppf = pd.DataFrame(samples_ppf)
    # Display summary
    print(df_ppf.head(1))
    return df_ppf

def create_gt_causal_chains(
        effect, 
        row_mech_causes, 
        row_root_causes,
        chain = []
):
    defects = [k for k, v in ishikawa_graph.items()if v.get("type", "") == "defect"]
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

def inject_defect_without_causes(df_ppf):
    rate = 0.001
    inject_count = int(rate * len(df_ppf))
    cols_to_check = ["Mechanism Failure Causes", "Defect occured", "Root Causes"]
    target_col = "Defect occured"
    mask = df_ppf[cols_to_check].applymap(lambda x: pd.isna(x) or x == "").all(axis=1)
    eligible_indices = df_ppf[mask].index
    # Randomly pick subset to inject
    inject_indices = random.sample(list(eligible_indices), min(inject_count, len(eligible_indices)))
    # Inject dynamic values based on index
    for idx in inject_indices:
        df_ppf.loc[idx, target_col] = f"SolderBridging_PCB{idx + 1}"

#this is hardcoded right now
def inject_spec_violations(df_ppf):
    inject_count = 2
    cols_to_check = ["metal load"]
    target_col = ["Paste viscosity"]
    mask = df_ppf[cols_to_check].applymap(lambda x: not pd.isna(x) and x < 70.0).all(axis=1)
    eligible_indices = df_ppf[mask].index
    # Randomly pick subset to inject
    inject_indices = random.sample(list(eligible_indices), min(inject_count, len(eligible_indices)))
    # Inject dynamic values based on index
    for idx in inject_indices:
        df_ppf.loc[idx, target_col] = 149.555

def generate_ground_truth(reuse=False):
    df_ppf = None
    if reuse:
        df_ppf = pd.read_csv(f"{output_path}/data.csv")
        inject_spec_violations(df_ppf)
    else:
        df_ppf = data_factory(size=5000)
        inject_spec_violations(df_ppf)

    # --- Apply to DataFrame ---
    root_cause_list = []
    mechanism_failure_list = []
    defect_list = []
    pcb_ids = []
    pcb_chains = {}

    out_of_specs_per_param = {
        k.lower():{"upper": 0, "lower": 0} for k,v in process_parameters.items()
    }
    for index, row in df_ppf.iterrows():
        row_root_causes = []
        row_mech_causes = []
        defects = []

        pcb_ids.append(f"PCB{index+1}")

        for param_name, spec in process_parameters.items():
            causes, mech_causes = get_causes(
                param_name.lower(), 
                row[param_name], 
                spec['LSL'], 
                spec['USL'], 
                index,
                out_of_specs_per_param
            )
            row_root_causes.extend(causes)
            row_mech_causes.extend(mech_causes)
        
        #ishikawa rules - mech causes
        process_parameters_temp = {create_classname_syntax(k): v for k,v in process_parameters.items()}
        for effect, effect_info in ishikawa_graph.items():
            causes = effect_info['caused_by']
            rules = effect_info.get('rules', [])
            for rule in rules:
                before_eq = rule.split("==")[0].replace("If", "").strip()
                pattern = r'([A-Za-z_][A-Za-z0-9_]*)\s*(<=|>=|<|>)\s*([A-Za-z_][A-Za-z0-9_]*)'
                pairs = re.findall(pattern, before_eq)
                result = {left: right for (left, op, right) in pairs}
                result_with_nums = {}
                obs_data = {create_classname_syntax(k) : v for k,v in row.to_dict().items()}
                for k, v in result.items():
                    result_with_nums[k] = obs_data[k]
                    result_with_nums[v] = process_parameters_temp[k][v.split("_")[1]]
                expr = before_eq.replace("AND", "and").replace("OR", "or")
                aeval.symtable.update(result_with_nums)
                rule_parsing_res = aeval(expr)
                if effect_info.get('type', "mech") != "defect" and rule_parsing_res:
                    row_mech_causes.append(effect)
        
        #Optional
        # if len(row_root_causes) == 0 and len(row_mech_causes) > 0:
        #     row_root_causes.extend(row_mech_causes)

        #DOUBTFUL
        if "NonCoalescence" in row_mech_causes or "InsufficientPasteVolumePerAperture" in row_mech_causes:
            defects.append(f"OpenCircuit_PCB{index+1}")
        if "ExcessReflowSpreading" in row_mech_causes or "ExcessPasteVolumePerAperture" in row_mech_causes:
            defects.append(f"SolderBridging_PCB{index+1}")
        
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
                            row_mech_causes_dup.pop(0), row_mech_causes_dup, row_root_causes, []
                        )
                    chain.extend(chain_a)
                # else:
                #     chain.append(row_root_causes)
            pcb_chains[f"PCB{index+1}"] = chain

        root_cause_list.append(", ".join(list(set(row_root_causes))))
        mechanism_failure_list.append(", ".join(list(set(row_mech_causes))))
        defect_list.append(", ".join(list(set(defects))))

    df_ppf['PCB_ID'] = pcb_ids
    df_ppf["Root Causes"] = root_cause_list
    df_ppf["Mechanism Failure Causes"] = mechanism_failure_list
    df_ppf["Defect occured"] = defect_list
    # Display summary
    print(df_ppf.head(1))

    inject_defect_without_causes(df_ppf)

    cols = ["PCB_ID"] + [col for col in df_ppf.columns if col != "PCB_ID"]
    df_ppf = df_ppf[cols]

    df_ppf.to_csv(f"{input_path}/data.csv", index=False)

    with open(f"{input_path}/test_chains.json", "w") as f:
        json.dump(pcb_chains, f, indent=1)
    
    with open(f"{output_path}/out_of_spec_data.json", "w") as f:
        json.dump(out_of_specs_per_param, f, indent=1)

# sigma_percent()

# generate_ground_truth(reuse=True)
# generate_ground_truth(reuse=False)
