from .base import FamilyBase, Payload
from . import cell_value_injection
from . import retrieved_document_poisoning
from . import mcp_tool_description_poisoning

FAMILIES: dict[str, FamilyBase] = {
    cell_value_injection.FAMILY.name: cell_value_injection.FAMILY,
    retrieved_document_poisoning.FAMILY.name: retrieved_document_poisoning.FAMILY,
    mcp_tool_description_poisoning.FAMILY.name: mcp_tool_description_poisoning.FAMILY,
}


def get(name: str) -> FamilyBase:
    if name not in FAMILIES:
        raise KeyError(f"unknown family {name!r}; known: {sorted(FAMILIES)}")
    return FAMILIES[name]
