import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class ExtractedData:
    specs: Dict
    manufacturing_processes: List[str]
    equipments: List[Dict]
    material_products: List[Dict]
    failure_data: Dict
    axioms: Dict
    definitions: Dict

@dataclass
class PipelineRunTime:
    mode: str
    create_ontology: bool
    data_rows: int
    factory_data: Optional[Any] = None
    chain_gt: Optional[Any] = None

@dataclass
class PipelineContext:
    data: ExtractedData
    runtime: PipelineRunTime