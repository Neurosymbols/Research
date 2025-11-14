import json, math, yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

input_path = f"./app/data/input/epoch3-7"

with open(f"{input_path}/surrogate_warpage_config.yml", "r") as f:
    CFG = yaml.safe_load(f)

pads = pd.read_csv(f"{input_path}/pads.csv")
print(pads.head(2))


#Piecewise‑linear temperature vs. time. T_of_t(t) returns the temperature at time t, and time_of_T(T) returns the first time T is reached.
def T_of_t(t, oven=CFG['oven_profile']):
    for ph in oven['phases']:
        if ph['t_start_s'] <= t <= ph['t_end_s']:
            f = (t - ph['t_start_s']) / (ph['t_end_s'] - ph['t_start_s'])
            return ph['T_start_C'] + f * (ph['T_end_C'] - ph['T_start_C'])
    if t < oven['phases'][0]['t_start_s']:
        return oven['phases'][0]['T_start_C']
    if t > oven['phases'][-1]['t_end_s']:
        return oven['phases'][-1]['T_end_C']
    return oven['ambient_C']

def time_of_T(T, dt=0.5, tmax=None):
    oven = CFG['oven_profile']
    if tmax is None:
        tmax = oven['phases'][-1]['t_end_s']
    t = 0.0
    while t <= tmax:
        if T_of_t(t) >= T:
            return t
        t += dt
    return None

# Curvature: [ \kappa(t) = K_s S_{cu} (\Delta\alpha \Delta T(t)) / h_{eff} \cdot R(T) ]
# Warpage at pad (small deflection): ( w = 0.5 \kappa r^2 ), returned in μm.
def logistic(x, k=0.08):
    return 1.0 / (1.0 + math.exp(-k * x))

def effective_thickness_mm(board_t, pkg_t):
    return 0.5 * board_t + 0.5 * pkg_t

def stiffness_boost(cu_fraction):
    return 1.0 + 0.8 * cu_fraction

def curvature_kappa_per_mm(t, cfg=CFG):
    b = cfg['board']; p = cfg['package']; s = cfg['stackup']; m = cfg['model']['analytic_params']
    ambient = cfg['oven_profile']['ambient_C']
    deltaT = T_of_t(t) - ambient
    delta_alpha = (b['cte_ppm_per_C'] - p['cte_ppm_per_C']) * 1e-6
    h_eff = effective_thickness_mm(b['thickness_mm'], p['thickness_mm'])
    R = 1.0 - m['visco_relax'] * logistic(T_of_t(t) - b['glass_transition_Tg_C'])
    S = stiffness_boost(s['copper_fraction'])
    K_s = m['kappa_scale']
    return K_s * S * R * (delta_alpha * deltaT) / max(h_eff, 1e-6)

def rnp_mm(x, y):
    return float((x**2 + y**2) ** 0.5)

def warpage_um_at_pad(x, y, t, noise=True, cfg=CFG):
    kappa = curvature_kappa_per_mm(t, cfg)
    r = rnp_mm(x, y)
    w_mm = 0.5 * kappa * (r ** 2)
    w_um = 1e3 * w_mm
    if noise:
        w_um += np.random.normal(0, cfg['model']['analytic_params']['noise_um_rms'])
    return float(w_um)

def predict_warpage(df, mode='analytic', noise=True):
    df = df.copy()
    if 't_s' not in df.columns and 'T_C' not in df.columns:
        raise ValueError("Provide either 't_s' or 'T_C'.")
    if 't_s' not in df.columns:
        df['t_s'] = df['T_C'].apply(lambda T: time_of_T(T) if pd.notnull(T) else np.nan)
    df['warpage_um'] = [
        warpage_um_at_pad(x, y, t, noise=noise)
        for x, y, t in zip(df['x_mm'], df['y_mm'], df['t_s'])
    ]
    return df

peak_t = time_of_T(240)
df_in = pads.copy()
df_in['t_s'] = peak_t
pred = predict_warpage(df_in, noise=False)
print(pred)

# time = []
# temp = []
# for i in range(0, 361):
#     time.append(i)
#     temp.append(T_of_t(i))

# plt.figure(figsize=(7,4))
# plt.plot(time, temp, marker='o')

# plt.xlabel("Time")
# plt.ylabel("Temperature (°C)")
# plt.title("Temperature vs Time")
# plt.grid(True)
# plt.tight_layout()
# plt.savefig("plot.png", dpi=300, bbox_inches="tight")