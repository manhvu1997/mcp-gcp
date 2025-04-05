"""
Data models for GKE cluster and nodepool management.
"""
from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field

from src.server.config import GCP_REGION, GCP_ZONE

class NodeTaint(BaseModel):
    """Model representing a Kubernetes node taint."""
    key: str
    value: str
    effect: Literal["NO_SCHEDULE", "PREFER_NO_SCHEDULE", "NO_EXECUTE"] = "NO_SCHEDULE"


class NodePool(BaseModel):
    """Model representing a GKE node pool."""
    name: str
    node_count: int = 3
    machine_type: str = "e2-standard-2"
    disk_size_gb: int = 100
    disk_type: Literal["pd-standard", "pd-balanced", "pd-ssd"] = "pd-standard"
    max_pods_per_node: int = 110
    network_tags: List[str] = Field(default_factory=list)
    kubernetes_labels: Dict[str, str] = Field(default_factory=dict)
    labels: Dict[str, str] = Field(default_factory=dict)
    taints: List[NodeTaint] = Field(default_factory=list)
    autoscaling_enabled: bool = False
    min_node_count: Optional[int] = None
    max_node_count: Optional[int] = None
    

class GKECluster(BaseModel):
    """Model representing a GKE cluster."""
    name: str
    location: str = Field(default_factory=lambda: GCP_REGION)
    location_type: Literal["zonal", "regional"] = "regional"
    autopilot: bool = False
    node_pools: List[NodePool] = Field(default_factory=list)
    cluster_ipv4_cidr: Optional[str] = None  # Pod address range
    services_ipv4_cidr: Optional[str] = None  # Service address range
    private_cluster: bool = False
    network: Optional[str] = None  # VPC network
    subnetwork: Optional[str] = None  # Subnetwork
    enable_private_nodes: bool = False
    enable_private_endpoint: bool = False
    master_ipv4_cidr_block: Optional[str] = None  # For private clusters
    kubernetes_version: Optional[str] = None
    
    @property
    def is_regional(self) -> bool:
        """Return True if the cluster is regional, False if zonal."""
        return self.location_type == "regional"


class GKEOperation(BaseModel):
    """Model representing a GKE operation result."""
    name: str
    status: str
    operation_type: str
    target_id: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    zone: Optional[str] = None
    region: Optional[str] = None