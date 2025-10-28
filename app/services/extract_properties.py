from rdflib import Graph, Namespace, BNode, URIRef
from rdflib.namespace import RDF, RDFS, OWL, SKOS
import sys, csv

base_path = "./app/data"
output_path = f"{base_path}/output/epoch3-7"
path = f"{base_path}/ontologies/epoch3-7"

def list_union_members(g, head):
    items = []
    cur = head
    while cur and cur != RDF.nil:
        first = next(g.objects(cur, RDF.first), None)
        if first is not None:
            items.append(first)
        cur = next(g.objects(cur, RDF.rest), None)
    return items

def render_expr(g, node):
    """Return a simple string for a class expression."""
    # Named class
    if isinstance(node, URIRef):
        return str(node)

    # unionOf
    u = next(g.objects(node, OWL.unionOf), None)
    if u:
        parts = [render_expr(g, it) for it in list_union_members(g, u)]
        return " OR ".join(parts)

    # intersectionOf
    i = next(g.objects(node, OWL.intersectionOf), None)
    if i:
        parts = [render_expr(g, it) for it in list_union_members(g, i)]
        # add parentheses if nested unions exist inside
        pretty = " AND ".join(parts)
        return f"({pretty})" if (" OR " in pretty) else pretty

    # complementOf
    c = next(g.objects(node, OWL.complementOf), None)
    if c:
        inner = render_expr(g, c)
        need_paren = (" AND " in inner) or (" OR " in inner)
        return f"NOT ({inner})" if need_paren else f"NOT {inner}"

    # default fallback
    return str(node)

def get_vals(g, s, p):
    """
    Return a list containing:
      - IRIs (as str) for simple named classes
      - ONE string for complex expressions (intersection/complement)
      - For unionOf: a flat list of members (each member can still be a complex string)
    """
    vals = []
    for o in g.objects(s, p):
        if isinstance(o, BNode):
            # Try union first: return all its members (each rendered)
            u = next(g.objects(o, OWL.unionOf), None)
            if u:
                for it in list_union_members(g, u):
                    vals.append(render_expr(g, it))
                continue

            # intersection / complement: return ONE rendered string
            i = next(g.objects(o, OWL.intersectionOf), None)
            c = next(g.objects(o, OWL.complementOf), None)
            if i or c:
                vals.append(render_expr(g, o))
                continue

            # unknown blank structure → best effort
            vals.append(render_expr(g, o))
        else:
            # Named class → plain IRI string
            vals.append(str(o))

    # De-dup and keep stable-ish order
    seen, out = set(), []
    for v in vals:
        if v not in seen:
            seen.add(v); out.append(v)
    return out

def get_label(g, iri):
    # Accept either a URIRef or a string
    if iri is None:
        return ""
    if isinstance(iri, str):
        iri = URIRef(iri)

    # rdfs:label (prefer @en)
    labels = list(g.objects(iri, RDFS.label))
    for l in labels:
        if getattr(l, "language", None) == "en":
            return str(l)
    if labels:
        return str(labels[0])

    # optional extra: try skos:prefLabel
    pref = next(g.objects(iri, SKOS.prefLabel), None)
    if pref:
        return str(pref)

    # final fallback: local name
    s = str(iri)
    if "#" in s and s.rfind("#") > s.rfind("/"):
        return s[s.rfind("#")+1:]
    return s.rsplit("/", 1)[-1]

def direct_parents(g, prop):
    """Immediate super-properties via rdfs:subPropertyOf (no transitive closure)."""
    return sorted(set(g.objects(prop, RDFS.subPropertyOf)), key=lambda x: str(x))

def load_with_imports(paths_or_iris):
    """Parse each input file/IRI and recursively load owl:imports."""
    g = Graph()
    seen = set()
    def _load_one(target):
        if target in seen:
            return
        seen.add(target)
        g.parse(target)
        for imp in g.objects(None, OWL.imports):
            _load_one(str(imp))
    for t in paths_or_iris:
        _load_one(t)
    return g

# owl_file = open("./Core.rdf")
g = load_with_imports([f'{path}/neurosymbols-causal-terminology.owl'])

rows=[]

for p in sorted(set(g.subjects(RDF.type, OWL.ObjectProperty)), key=lambda x: str(x)):
    ds = get_vals(g, p, RDFS.domain) or [None]
    rs = get_vals(g, p, RDFS.range)  or [None]

    # parents
    parents = direct_parents(g, p)
    parent_iris = " | ".join(str(pp) for pp in parents) if parents else ""
    parent_labels = " | ".join(get_label(g, pp) for pp in parents) if parents else ""
    first_parent = parents[0] if parents else None
    first_parent_iri = str(first_parent) if first_parent else ""
    first_parent_label = get_label(g, first_parent) if first_parent else ""


    for d in ds:
        for r in rs:
            rows.append({
                "property_iri": str(p),
                "property_label": get_label(g, p),
                "domain_iri":  "" if d is None else str(d),
                "domain_label": "" if d is None else get_label(g, d),
                "range_iri":   "" if r is None else str(r),
                "range_label": "" if r is None else get_label(g, r),
                "parent_iris": parent_iris,
                "parent_labels": parent_labels,
                "first_parent_iri": first_parent_iri,
                "first_parent_label": first_parent_label,
            })

fieldnames = [
    "property_iri","property_label",
    "domain_iri","domain_label",
    "range_iri","range_label",
    "parent_iris","parent_labels",
    "first_parent_iri","first_parent_label"
]
w = csv.DictWriter(open(f"{output_path}/object_properties.csv", "w"), fieldnames=fieldnames)
w.writeheader(); w.writerows(rows)

