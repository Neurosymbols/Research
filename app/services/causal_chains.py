import json
import pandas as pd
import random
import re

from lark import Lark, Transformer

from .utils import perform_sparql_query, perform_sparql_update

CAUSAL_CHAIN_PATH = "./app/data/input/epoch3-7/causal_chain.json"
SPARQL_QUERIES = "./app/data/input/epoch3-7/queries.txt"
STRUCTURED_RULES_PATH = "./app/data/output/epoch3-7/structured_rules.json"
RULE_QUERY_MAP_PATH = "./app/data/output/epoch3-7/rules_query.txt"
FAILURE_CAUSES = pd.read_csv("./app/data/input/epoch3-7/defects_and_failure_causes.csv")
failure_cause_ca_mapping = dict(zip(FAILURE_CAUSES['item'], FAILURE_CAUSES['corrective action']))

STRUCTURED_RULE_MAP = {}
RULE_QUERY_MAP = {}

with open(CAUSAL_CHAIN_PATH) as f:
    CAUSAL_CHAIN_OBJ = json.load(f)

# for one product and one failure mechanism, multiple rules can fire. Using product name and failure cause name is necessary but not enough to create a unique identiier for coa individuals. It needs rule id too

template_sparql = """
    PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
    PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
    PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
    PREFIX bfo: <http://purl.obolibrary.org/obo/>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    {VERB} { 
    ?coa a term:ConformanceAssessment ;
        term:triggeredByRule "{RULE}" ;
        term:realizationOf ?disposition ;
    {RELATED_OBS_BINDINGS}
        rdfs:label ?coa_label .
    ?fc a term:{EFFECT} ;
        prov:wasGeneratedBy ?coa ;
        term:affects ?product ;
        rdfs:label ?fc_label .
    } WHERE {
    ?disposition a term:{EFFECT}Disposition .
    {OBS_BINDINGS}
    {LIMIT_BINDINGS}
    FILTER({FILTER_EXPR})
    BIND(IRI(CONCAT(str(assert:), "COA-", STRAFTER(STR(?product), "#"), "-",'{RULE_ID}')) AS ?coa)
    BIND(CONCAT("COA-", STRAFTER(STR(?product), "#"), "-", '{RULE_ID}') AS ?coa_label)
    BIND(IRI(CONCAT(str(assert:), "FC-", "{EFFECT}-", STRAFTER(STR(?product), "#"))) AS ?fc)
    BIND(CONCAT("{EFFECT}") AS ?fc_label)
    }
"""

LIMIT_TO_SPEC_PROP = {
    "LSL": "hasLowerValue",
    "USL": "hasUpperValue",
    "NOM": "hasNominalValue",
    "threshold": "hasThresholdValue"
}

def parse_rule(rule_str:str):
    grammar = r"""
        start: "If" expr "==" effects
        effects: NAME ("OR" NAME)*
        expr: expr "AND" expr   -> and_
            | expr "OR" expr   -> or_
            | cond
            | "(" expr ")"
        cond: NAME OP (NAME | NUMBER)
        OP: "<="|">="|"<"|">"|"="|"≤"|"≥"
        NAME: /[A-Za-z_][A-Za-z0-9_]*/
        NUMBER: /[0-9]+(\.[0-9]+)?/
        %import common.WS
        %ignore WS
    """

    parser = Lark(grammar, start="start")

    class ToDict(Transformer):
        def NAME(self, tk): return tk.value
        def OP(self, tk):
            # normalize Unicode operators to ASCII
            val = tk.value
            if val == "≤":
                val = "<="
            elif val == "≥":
                val = ">="
            return val
        def cond(self, args):  # NAME OP NAME
            left, op, right = args
            limit = right.split("_")[-1] if "_" in right else right
            return {"obs": left, "operator": op, "limit": limit}
        def and_(self, args):
            flat = []
            for a in args:
                if isinstance(a, dict) and a.get("logic") == "AND":
                    flat.extend(a["subconditions"])
                else:
                    flat.append(a)
            return {"logic": "AND", "subconditions": flat}
        def or_(self, args):
            flat = []
            for a in args:
                if isinstance(a, dict) and a.get("logic") == "OR":
                    flat.extend(a["subconditions"])
                else:
                    flat.append(a)
            return {"logic": "OR", "subconditions": flat}
        def effects(self, args): return [a for a in args]
        def expr(self, args):
            # unwrap nested expr trees automatically
            if len(args) == 1:
                return args[0]
            return args
        def start(self, args):
            expr, eff = args
            # if expr is a single AND/OR dict, wrap as list
            if isinstance(expr, dict):
                exprs = [expr]
            elif isinstance(expr, list):
                exprs = expr
            else:
                exprs = [expr]
            return {"conditions": exprs, "effects": eff}
    structured_rule = ToDict().transform(parser.parse(rule_str))
    return structured_rule

def gen_related_obs(rule):
    """
    Recursively extract all unique observation names from nested conditions
    and generate:
      1. related_observation lines for CONSTRUCT
      2. effect name(s) for later per-effect SPARQL generation
    """
    seen = []

    def walk(node):
        if isinstance(node, dict):
            if "obs" in node:
                if node["obs"] not in seen:
                    seen.append(node["obs"])
            elif "subconditions" in node:
                for sub in node["subconditions"]:
                    walk(sub)
        elif isinstance(node, list):
            for sub in node:
                walk(sub)

    # Walk through all top-level conditions
    for cond in rule["conditions"]:
        walk(cond)

    # Generate the SPARQL lines
    related_lines = [
        f"""       term:hasAssessmentInput ?{o}_obs ;
                   term:hasAssessmentInput ?{o}_spec ;
        """ for o in seen]
    related_block = "\n".join(related_lines)

    return related_block

def gen_obs_bindings(rule):
    """
    Recursively generate all observation triple patterns used in the rule.
    Avoid duplicates if the same observation appears multiple times.
    """
    seen = set()
    blocks = []

    def walk(node):
        if isinstance(node, dict):
            if "obs" in node:
                obs = node["obs"]
                if obs not in seen:
                    seen.add(obs)
                    block = f"""  ?{obs}_obs a term:{obs}Obs ;
                                            term:hasObservedValue ?{obs}_obsvalue ;
                                            iof:isAbout ?{obs}_spec ;
                                            term:observationOf ?product .
                                   ?{obs}_spec a term:ParameterSpecification . 
                            """
                    blocks.append(block)
            elif "subconditions" in node:
                for sub in node["subconditions"]:
                    walk(sub)
        elif isinstance(node, list):
            for sub in node:
                walk(sub)

    for cond in rule["conditions"]:
        walk(cond)

    return "\n\n".join(blocks)

def spec_prop_for(token):
    """Map limit token to ontology property name"""
    return LIMIT_TO_SPEC_PROP.get(token, f"has{token.capitalize()}Value")

def gen_limit_bindings(rule):
    """
    Recursively extract all unique (observation, limit) pairs
    and generate spec triple lines.
    """
    seen = set()
    lines = []

    def walk(node):
        if isinstance(node, dict):
            if "obs" in node:
                obs = node["obs"]
                lim = node["limit"]
                if not lim.isdigit():
                    prop = spec_prop_for(lim)
                    key = (obs, prop)
                    if key not in seen:
                        seen.add(key)
                        lines.append(f"  ?{obs}_spec term:{prop} ?{obs}_specvalue .")
            elif "subconditions" in node:
                for sub in node["subconditions"]:
                    walk(sub)
        elif isinstance(node, list):
            for sub in node:
                walk(sub)

    for cond in rule["conditions"]:
        walk(cond)

    return "\n".join(lines)

def gen_filter_expr(rule):
    """
    Recursively generate FILTER expression for nested AND/OR conditions.
    Produces a valid SPARQL filter string.
    """

    def walk(node):
        if isinstance(node, dict):
            # Leaf node → observation comparison
            if "obs" in node:
                obs = node["obs"]
                op = node["operator"]
                limit = node['limit']
                if limit.isdigit():
                    return f"xsd:float(?{obs}_obsvalue) {op} xsd:float({limit})"
                else:
                    return f"xsd:float(?{obs}_obsvalue) {op} xsd:float(?{obs}_specvalue)"
            # Logical node (AND/OR)
            elif "logic" in node and "subconditions" in node:
                sub_exprs = [walk(sub) for sub in node["subconditions"]]
                if node["logic"] == "AND":
                    joined = " && ".join(sub_exprs)
                elif node["logic"] == "OR":
                    joined = " || ".join(sub_exprs)
                else:
                    raise ValueError(f"Unknown logic operator: {node['logic']}")
                return f"({joined})"
        elif isinstance(node, list):
            # for top-level conditions list
            return " && ".join([walk(sub) for sub in node])
        return ""

    # combine all top-level conditions with AND
    expr = " && ".join([walk(c) for c in rule["conditions"]])
    return expr

def rule_to_sparql_util(rule_str, rule_pk, verb):
    """
    Convert a full causal rule string (with →) into one or more SPARQL queries.
    Automatically detects all parameters and effects.
    """
    #checked. Prepare test cases
    structured_rule = parse_rule(rule_str)
    effects = structured_rule['effects']
    STRUCTURED_RULE_MAP[rule_str] = structured_rule
    #checked. Prepare test cases
    related_block_bindings = gen_related_obs(structured_rule)
    obs_bindings = gen_obs_bindings(structured_rule)
    limit_bindings = gen_limit_bindings(structured_rule)
    filter_bindings = gen_filter_expr(structured_rule)
    sparql_queries = []
    for effect in effects:
        rule_id = f"{effect}-rule-{rule_pk}"
        query = template_sparql.replace("{VERB}", verb)\
                        .replace("{RELATED_OBS_BINDINGS}", related_block_bindings)\
                        .replace("{EFFECT}", effect)\
                        .replace("{RULE_ID}", rule_id)\
                        .replace("{RULE}", rule_str)\
                        .replace("{OBS_BINDINGS}", obs_bindings)\
                        .replace("{LIMIT_BINDINGS}", limit_bindings)\
                        .replace("{FILTER_EXPR}", filter_bindings)
        sparql_queries.append(query)
        if rule_str not in RULE_QUERY_MAP:
            RULE_QUERY_MAP[rule_id] = {"name": rule_str, "queries": []}
        RULE_QUERY_MAP[rule_id]['queries'].append(query)

def rule_to_sparql(verb="CONSTRUCT"):
    for effect, effect_info in CAUSAL_CHAIN_OBJ.items():
        rules = effect_info.get('governed_by', [])
        rule_pk = 1
        for r in rules:
            rule_to_sparql_util(r, rule_pk, verb)
            rule_pk += 1
    with open(STRUCTURED_RULES_PATH, "w", encoding="utf-8") as f3:
        json.dump(STRUCTURED_RULE_MAP, f3, ensure_ascii=False, indent=2)
    with open(RULE_QUERY_MAP_PATH, "w", encoding="utf-8") as f3:
        json_str = json.dumps(RULE_QUERY_MAP, indent=2).encode('utf-8').decode('unicode_escape')
        f3.write(json_str)

def fire_failure_cause_queries(verb):
    rule_firing_report = {}
    for rule_id, rule_info in RULE_QUERY_MAP.items():
        for q in rule_info['queries']:
            if verb == "INSERT":
                perform_sparql_update(q)
            else:
                print(q)
                print("##################")
                construct_res = perform_sparql_query(q)
                rule_firing_report[rule_id] = len(construct_res)
    if verb == "CONSTRUCT":
        with open(f"./app/data/output/epoch3-7/failure_cause_rules_firing_report.json", "w") as f:
            json.dump(rule_firing_report, f, indent=2)

def create_causal_chain(verb):
    for effect, effect_info in CAUSAL_CHAIN_OBJ.items():
        for cause in effect_info['caused_by']:
            insert_query = f'''
                PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
                PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
                PREFIX ro: <http://purl.obolibrary.org/obo/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                {verb} {{
                    ?effect ro:RO_0002559 ?cause .
                    ?effect ro:directlyCausallyInfluencedBy ?cause .
                    ?effect rdf:type term:Effect .
                }}
                WHERE {{
                    ?effect a term:{effect} .
                    ?cause  a term:{cause} .
                    VALUES ?effect_pred {{ term:defectOccursOn term:affects }}
                    ?effect ?effect_pred ?product .
                    ?cause term:affects ?product .
                }}
                '''
            if verb == "INSERT":
                perform_sparql_update(insert_query)
            else:
                print(insert_query)
                print(len(perform_sparql_query(insert_query)))

def infere_root_causes(verb):
    root_cause_query = f'''
            PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
            PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
            PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
            PREFIX ro: <http://purl.obolibrary.org/obo/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        {verb} {{
                    ?fc a term:RootCause ;
                }}
                WHERE {{
                ?fc a term:FailureCause ;
                    term:affects ?product .
                ?product a iof:MaterialProduct . 
                FILTER NOT EXISTS {{ ?fc ro:RO_0002559 ?other . }}
        }}
    '''
    attach_root_cause_to_defect = f'''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX iof: <https://spec.industrialontologies.org/ontology/core/Core/>
        PREFIX ro: <http://purl.obolibrary.org/obo/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        {verb} {{
                    ?defect ro:RO_0002559 ?fc .
                }}
                WHERE {{
                ?fc a term:RootCause ;
                    term:affects ?product .
                ?defect a term:Defect ;
                    term:defectOccursOn ?product
        }}
    '''
    if verb == "INSERT":
        perform_sparql_update(root_cause_query)
        perform_sparql_update(attach_root_cause_to_defect)
    else:
        print(len(perform_sparql_query(root_cause_query)))
        print(len(perform_sparql_query(attach_root_cause_to_defect)))

def attach_corrective_action_to_root_causes(verb):
    query = '''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX ro: <http://purl.obolibrary.org/obo/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?rootcause ?effect

        WHERE {
                ?rootcause a term:RootCause ;
                        ro:RO_0002566 ?effect ;
                        term:affects ?product .
                ?effect a term:Defect .
            }
    '''
    ca_query_temp = f'''
        PREFIX term: <https://neurosymbols.ai/ontology/causal-terminology.owl#>
        PREFIX assert: <https://neurosymbols.ai/data/causal-assertions.owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        {verb} {{
            ?action a term:CorrectiveAction ;
                    rdfs:label ?action_label .
            ?fc term:isCorrectedBy ?action .
        }}
        WHERE{{
            ?fc a term:RootCause ;
                term:affects ?product .
    		FILTER(STR(?fc) = "{{fc_uri}}")
            BIND(IRI("assert:{{ca_uri}}") as ?action)
            BIND("{{ca_label}}" as ?action_label)
        }}
    '''
    results = perform_sparql_query(query)
    for binding in results['results']['bindings']:
        if binding:
            rootcause = binding.get('rootcause').get('value')
            rootcauselabel = rootcause.split('#')[1]
            #TODO: improve this. This is hardcoding
            rootcauselabel_splits = rootcause.split("#")[1].split("-")
            #ensures the label is of structure FC-{rootcausename}-{pcb id}
            if len(rootcauselabel_splits) == 3:
                rootcauseclass = rootcauselabel_splits[1]
                ca_label = failure_cause_ca_mapping[rootcauseclass]
                effect = binding.get('effect').get('value')
                corrective_action_uri = f"CA-{rootcauselabel}-{effect.split('#')[1]}"
                ca_query = ca_query_temp.replace("{fc_uri}", rootcause)\
                            .replace("{ca_uri}", corrective_action_uri)\
                            .replace("{ca_label}", ca_label)
                if verb == "INSERT":
                    perform_sparql_update(ca_query)
                else:
                    print(ca_query)
                    print(len(perform_sparql_query(ca_query)))


# rule_to_sparql(verb="INSERT")
# fire_failure_cause_queries(verb="INSERT")
# create_causal_chain(verb="INSERT")
# infere_root_causes(verb="INSERT")
# attach_corrective_action_to_root_causes(verb="INSERT")


        