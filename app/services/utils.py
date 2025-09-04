import re
def extract_floats(s):
    # Match optional sign, digits, optional decimal part
    return [float(num) for num in re.findall(r'[-+]?\d*\.\d+|[-+]?\d+', s)]

def sum_nos(arr):
    total = math.fsum(arr)
    max_dp = 0
    for v in arr:
        s = str(v)
        if '.' in s:
            dp = len(s.split('.')[1])
            if dp > max_dp:
                max_dp = dp
    return round(total, max_dp)

def get_spec_values(v:str):
    specs = {"NV": 0.0, "UL": 0.0, "LL": 0.0}
    comp_signs = ["<", ">", "≥"]
    comp_sign_pat = "|".join(map(re.escape, comp_signs))
    if "±" in v:
        floats = extract_floats(v)
        specs['NV'] = floats[0]
        specs['UL'] = sum_nos(floats)
        specs['LL'] = sum_nos([floats[0], -floats[1]])
        specs['tolerance'] = floats[1]
    if re.search(comp_sign_pat, v):
        floats = extract_floats(v)
        specs['NV'] = floats[0]
    return specs