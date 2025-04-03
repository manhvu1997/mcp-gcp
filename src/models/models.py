
import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field
from src.server.config import GCP_ZONE
# Models
class GCPInstance(BaseModel):
    """Model representing a GCP instance."""
    name: str
    machine_type: str = "n1-standard-1"
    zone: str = Field(default_factory=lambda: GCP_ZONE)
    status: Optional[str] = None
    network_interfaces: List[Dict[str, Any]] = Field(default_factory=list)
    disks: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    labels: Dict[str, str] = Field(default_factory=dict)
    source_image: str = "projects/debian-cloud/global/images/family/debian-10"

    class Config:
        arbitrary_types_allowed = True


class GCPInstanceList(BaseModel):
    """Model representing a list of GCP instances."""
    instances: List[GCPInstance] = Field(default_factory=list)
    next_page_token: Optional[str] = None


class GCPOperationResult(BaseModel):
    """Model representing a GCP operation result."""
    name: str
    status: str
    operation_type: str
    target_id: Optional[str] = None
    error: Optional[Dict[str, Any]] = None