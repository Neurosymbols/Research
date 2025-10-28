from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS, OWL
import sys, csv

base_path = "./app/data"
output_path = f"{base_path}/output/epoch3-7"
path = f"{base_path}/ontologies/epoch3-7"


def get_label(g, iri):
    if not isinstance(iri, URIRef):
        return ""
    lbl = next(g.objects(iri, RDFS.label), None)
    return str(lbl) if lbl else ""

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

rows = []

# Find all classes
classes = set(g.subjects(RDF.type, OWL.Class))
classes.update(g.subjects(RDFS.subClassOf, None))  # also catch classes only used in subclass axioms

for c in sorted(classes, key=lambda x: str(x)):
    if isinstance(c, URIRef):
        parents = [p for p in g.objects(c, RDFS.subClassOf) if isinstance(p, URIRef)]
        if not parents:
            parents = [None]
        for p in parents:
            rows.append({
                "class_iri": str(c),
                "class_label": get_label(g, c),
                "parent_iri": "" if p is None else str(p),
                "parent_label": "" if p is None else get_label(g, p),
            })

# Write CSV to stdout
writer = csv.DictWriter(open(f"{output_path}/classes.csv", "w"), fieldnames=["class_iri","class_label","parent_iri","parent_label"])
writer.writeheader()
writer.writerows(rows)