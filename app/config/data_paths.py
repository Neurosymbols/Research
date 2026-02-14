from dataclasses import dataclass
from pathlib import Path

BASE = Path("./app/data")
EPOCH = "epoch3-8" 

@dataclass(frozen=True)
class Folders:
    onto: Path = BASE / "ontologies" / EPOCH
    input: Path = BASE / "input" / EPOCH
    output: Path = BASE / "output" / EPOCH

@dataclass(frozen=True)
class Files:
    properties: Path
    specs: Path
    failure_causes: Path
    equipments: Path
    axioms: Path
    ft_data: Path
    test_data: Path
    ft_chains: Path
    test_chains: Path
    ishikawa: Path
    specs_json: Path
    classes_define: Path
    object_props_define: Path

@dataclass(frozen=True)
class Ontologies:
    bfo_prov: Path
    bfo : Path
    iof : Path
    ro : Path
    skos: Path
    terms : Path
    assertions : Path

folders = Folders()

resources = Files(
    properties = folders.input / "ontology_properties.yml",
    specs = folders.input / "specs_data.csv",
    failure_causes = folders.input / "defects_and_failure_causes.csv",
    equipments = folders.input / "equipment_data.csv",
    axioms = folders.input / "axioms.csv",
    ft_data = folders.input / "synthetic_data_factory_ft.csv",
    test_data = folders.input / "synthetic_data_factory_test.csv",
    ft_chains = folders.input / "causal_test_cases_ft.json",
    test_chains = folders.input / "causal_test_cases_test.json",
    ishikawa = folders.input / "causal_chain.json",
    specs_json = folders.input / "specs.json",
    classes_define = folders.input / "classes_def.csv",
    object_props_define = folders.input / "object_rels_def.csv"
)

ontologies = Ontologies(
    bfo_prov = folders.onto / "bfo-prov.owl",
    bfo = folders.onto / "bfo.owl",
    iof = folders.onto / "iof-core.rdf",
    ro = folders.onto / "ro-causal-properties.owl",
    skos = folders.onto / "skos.rdf",
    terms = folders.onto / "causal-terminology.owl",
    assertions = folders.onto / "causal-assertions.owl"
)