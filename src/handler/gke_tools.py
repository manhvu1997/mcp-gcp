import logging
import asyncio
from typing import Dict, List, Optional, Any, Literal, Union

from src.core.gke_service import GKEService
from src.models.gke_models import GKECluster, NodePool, NodeTaint

logger = logging.getLogger(__name__)

class GKETools:
    """
    Collection of GKE cluster and nodepool management tools for MCP.
    """
    
    def __init__(self, gke_service: GKEService, mcp):
        """
        Initialize with a GKE service and MCP instance.
        
        Args:
            gke_service: GKE service instance
            mcp: MCP instance for registering tools
        """
        self.gke_service = gke_service
        self.mcp = mcp
        self.register_tools()
    
    def register_tools(self):
        """Register all GKE tools with MCP."""
        
        # List clusters tool
        @self.mcp.tool()
        async def list_gke_clusters(location: Optional[str] = None) -> str:
            """
            List all GKE clusters in the specified location or across all locations.
            
            Args:
                location: The zone or region to list clusters from (optional, e.g. us-central1 or us-central1-a)
            """
            try:
                clusters = self.gke_service.list_clusters(location)
                
                if not clusters:
                    return f"No GKE clusters found{' in ' + location if location else ''}."
                
                # Format the response
                result = f"GKE Clusters{' in ' + location if location else ''}:\n\n"
                for cluster in clusters:
                    cluster_type = "Autopilot" if cluster.autopilot else "Standard"
                    result += f"- {cluster.name} ({cluster_type})\n"
                    result += f"  Location: {cluster.location} ({cluster.location_type})\n"
                    result += f"  Kubernetes Version: {cluster.kubernetes_version or 'unknown'}\n"
                    result += f"  Node Pools: {len(cluster.node_pools)}\n"
                    result += "\n"
                
                return result
            except Exception as e:
                logger.error(f"Error listing GKE clusters: {e}")
                return f"Failed to list GKE clusters: {str(e)}"
        
        # Get cluster details tool
        @self.mcp.tool()
        async def get_gke_cluster(name: str, location: str) -> str:
            """
            Get details for a specific GKE cluster.
            
            Args:
                name: The name of the cluster
                location: The zone or region where the cluster is located (e.g. us-central1 or us-central1-a)
            """
            try:
                cluster = self.gke_service.get_cluster(name, location)
                
                if not cluster:
                    return f"GKE cluster '{name}' not found in location {location}."
                
                # Format the response
                result = f"GKE Cluster: {cluster.name}\n"
                result += f"  Location: {cluster.location} ({cluster.location_type})\n"
                result += f"  Type: {'Autopilot' if cluster.autopilot else 'Standard'}\n"
                result += f"  Kubernetes Version: {cluster.kubernetes_version or 'unknown'}\n"
                
                # Add network information
                result += "  Network Configuration:\n"
                result += f"    VPC Network: {cluster.network or 'default'}\n"
                result += f"    Subnetwork: {cluster.subnetwork or 'default'}\n"
                result += f"    Pod Address Range: {cluster.cluster_ipv4_cidr or 'auto'}\n"
                result += f"    Service Address Range: {cluster.services_ipv4_cidr or 'auto'}\n"
                result += f"    Private Cluster: {'Yes' if cluster.private_cluster else 'No'}\n"
                
                if cluster.private_cluster:
                    result += f"    Master CIDR Block: {cluster.master_ipv4_cidr_block}\n"
                    result += f"    Private Nodes: {'Yes' if cluster.enable_private_nodes else 'No'}\n"
                    result += f"    Private Endpoint: {'Yes' if cluster.enable_private_endpoint else 'No'}\n"
                
                # Add node pool information
                if not cluster.autopilot:
                    result += "\n  Node Pools:\n"
                    for pool in cluster.node_pools:
                        result += f"    - {pool.name}\n"
                        result += f"      Nodes: {pool.node_count}\n"
                        result += f"      Machine Type: {pool.machine_type}\n"
                        result += f"      Disk: {pool.disk_size_gb}GB ({pool.disk_type})\n"
                        result += f"      Max Pods Per Node: {pool.max_pods_per_node}\n"
                        
                        if pool.autoscaling_enabled:
                            result += f"      Autoscaling: {pool.min_node_count} to {pool.max_node_count} nodes\n"
                        
                        if pool.kubernetes_labels:
                            result += "      Kubernetes Labels:\n"
                            for k, v in pool.kubernetes_labels.items():
                                result += f"        {k}: {v}\n"
                        
                        if pool.network_tags:
                            result += f"      Network Tags: {', '.join(pool.network_tags)}\n"
                        
                        if pool.taints:
                            result += "      Taints:\n"
                            for taint in pool.taints:
                                result += f"        {taint.key}={taint.value}:{taint.effect}\n"
                
                return result
            except Exception as e:
                logger.error(f"Error getting GKE cluster details: {e}")
                return f"Failed to get details for GKE cluster '{name}' in location {location}: {str(e)}"
        
        # Create cluster tool
        @self.mcp.tool()
        async def create_gke_cluster(
            name: str,
            location: str,
            location_type: Literal["zonal", "regional"] = "regional",
            autopilot: bool = False,
            network: Optional[str] = None,
            subnetwork: Optional[str] = None,
            pod_address_range: Optional[str] = None,
            service_address_range: Optional[str] = None,
            private_cluster: bool = False,
            enable_private_nodes: Optional[bool] = None,
            enable_private_endpoint: Optional[bool] = None,
            master_cidr_block: Optional[str] = None,
            kubernetes_version: Optional[str] = None
        ) -> str:
            """
            Create a new GKE cluster with optional node pools.
            
            Args:
                name: Name for the new cluster
                location: Region or zone to create the cluster in (e.g. us-central1 or us-central1-a)
                location_type: "zonal" or "regional" (regional clusters have higher availability)
                autopilot: Whether to create an Autopilot cluster (managed by Google)
                network: The VPC network to use (e.g. "default")
                subnetwork: The subnetwork to use (e.g. "default")
                pod_address_range: CIDR range for pod IPs (e.g. "10.4.0.0/14")
                service_address_range: CIDR range for service IPs (e.g. "10.8.0.0/20")
                private_cluster: Whether to create a private cluster
                enable_private_nodes: For private clusters, whether to use private nodes
                enable_private_endpoint: For private clusters, whether to use a private endpoint
                master_cidr_block: For private clusters, CIDR range for the master (e.g. "172.16.0.0/28")
                kubernetes_version: Kubernetes version to use (e.g. "1.27.3-gke.100")
            """
            try:
                # Set defaults for private cluster options if not specified
                if private_cluster:
                    enable_private_nodes = True if enable_private_nodes is None else enable_private_nodes
                    enable_private_endpoint = False if enable_private_endpoint is None else enable_private_endpoint
                    if not master_cidr_block:
                        return "When creating a private cluster, master_cidr_block must be specified."
                
                # Create cluster object
                cluster = GKECluster(
                    name=name,
                    location=location,
                    location_type=location_type,
                    autopilot=autopilot,
                    network=network,
                    subnetwork=subnetwork,
                    cluster_ipv4_cidr=pod_address_range,
                    services_ipv4_cidr=service_address_range,
                    private_cluster=private_cluster,
                    enable_private_nodes=enable_private_nodes,
                    enable_private_endpoint=enable_private_endpoint,
                    master_ipv4_cidr_block=master_cidr_block,
                    kubernetes_version=kubernetes_version
                )
                
                # Create the cluster
                result = self.gke_service.create_cluster(cluster)
                
                return f"Creating GKE cluster '{name}' in {location} ({location_type}). Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error creating GKE cluster: {e}")
                return f"Failed to create GKE cluster '{name}' in {location}: {str(e)}"
        
        # Create a standard cluster with node pools
        @self.mcp.tool()
        async def create_standard_gke_cluster(
            name: str,
            location: str,
            location_type: Literal["zonal", "regional"] = "regional",
            node_pool_name: str = "default-pool",
            machine_type: str = "e2-standard-2",
            node_count: int = 3,
            disk_size_gb: int = 100,
            disk_type: Literal["pd-standard", "pd-balanced", "pd-ssd"] = "pd-standard",
            max_pods_per_node: int = 110,
            network: Optional[str] = None,
            subnetwork: Optional[str] = None,
            pod_address_range: Optional[str] = None,
            service_address_range: Optional[str] = None,
            private_cluster: bool = False,
            master_cidr_block: Optional[str] = None,
            kubernetes_version: Optional[str] = None
        ) -> str:
            """
            Create a new standard GKE cluster with a default node pool.
            
            Args:
                name: Name for the new cluster
                location: Region or zone to create the cluster in (e.g. us-central1 or us-central1-a)
                location_type: "zonal" or "regional" (regional clusters have higher availability)
                node_pool_name: Name for the default node pool
                machine_type: Machine type for nodes (e.g. "e2-standard-2")
                node_count: Number of nodes to create
                disk_size_gb: Size of the boot disk in GB
                disk_type: Type of disk to use (standard, balanced, or SSD)
                max_pods_per_node: Maximum number of pods per node
                network: The VPC network to use (e.g. "default")
                subnetwork: The subnetwork to use (e.g. "default")
                pod_address_range: CIDR range for pod IPs (e.g. "10.4.0.0/14")
                service_address_range: CIDR range for service IPs (e.g. "10.8.0.0/20")
                private_cluster: Whether to create a private cluster
                master_cidr_block: For private clusters, CIDR range for the master (e.g. "172.16.0.0/28")
                kubernetes_version: Kubernetes version to use (e.g. "1.27.3-gke.100")
            """
            try:
                # Create node pool
                node_pool = NodePool(
                    name=node_pool_name,
                    node_count=node_count,
                    machine_type=machine_type,
                    disk_size_gb=disk_size_gb,
                    disk_type=disk_type,
                    max_pods_per_node=max_pods_per_node
                )
                
                # Set defaults for private cluster options
                enable_private_nodes = True if private_cluster else None
                enable_private_endpoint = False if private_cluster else None
                
                if private_cluster and not master_cidr_block:
                    return "When creating a private cluster, master_cidr_block must be specified."
                
                # Create cluster object
                cluster = GKECluster(
                    name=name,
                    location=location,
                    location_type=location_type,
                    autopilot=False,
                    node_pools=[node_pool],
                    network=network,
                    subnetwork=subnetwork,
                    cluster_ipv4_cidr=pod_address_range,
                    services_ipv4_cidr=service_address_range,
                    private_cluster=private_cluster,
                    enable_private_nodes=enable_private_nodes,
                    enable_private_endpoint=enable_private_endpoint,
                    master_ipv4_cidr_block=master_cidr_block,
                    kubernetes_version=kubernetes_version
                )
                
                # Create the cluster
                result = self.gke_service.create_cluster(cluster)
                
                return f"Creating standard GKE cluster '{name}' in {location} with node pool '{node_pool_name}'. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error creating standard GKE cluster: {e}")
                return f"Failed to create standard GKE cluster '{name}' in {location}: {str(e)}"
        
        # Delete cluster tool
        @self.mcp.tool()
        async def delete_gke_cluster(name: str, location: str) -> str:
            """
            Delete a GKE cluster.
            
            Args:
                name: The name of the cluster to delete
                location: The zone or region where the cluster is located
            """
            try:
                # Check if cluster exists
                existing = self.gke_service.get_cluster(name, location)
                if not existing:
                    return f"GKE cluster '{name}' not found in location {location}."
                
                # Delete the cluster
                result = self.gke_service.delete_cluster(name, location)
                
                return f"Deleting GKE cluster '{name}' in {location}. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error deleting GKE cluster: {e}")
                return f"Failed to delete GKE cluster '{name}' in {location}: {str(e)}"
        
        # List node pools tool
        @self.mcp.tool()
        async def list_gke_node_pools(cluster_name: str, location: str) -> str:
            """
            List all node pools in a GKE cluster.
            
            Args:
                cluster_name: The name of the cluster
                location: The zone or region where the cluster is located
            """
            try:
                # Check if cluster exists
                cluster = self.gke_service.get_cluster(cluster_name, location)
                if not cluster:
                    return f"GKE cluster '{cluster_name}' not found in location {location}."
                
                if cluster.autopilot:
                    return f"Cluster '{cluster_name}' is an Autopilot cluster, which does not have user-manageable node pools."
                
                node_pools = self.gke_service.list_node_pools(cluster_name, location)
                
                if not node_pools:
                    return f"No node pools found in GKE cluster '{cluster_name}'."
                
                # Format the response
                result = f"Node Pools in GKE Cluster '{cluster_name}':\n\n"
                for pool in node_pools:
                    result += f"- {pool.name}\n"
                    result += f"  Nodes: {pool.node_count}\n"
                    result += f"  Machine Type: {pool.machine_type}\n"
                    result += f"  Disk: {pool.disk_size_gb}GB ({pool.disk_type})\n"
                    result += f"  Max Pods Per Node: {pool.max_pods_per_node}\n"
                    
                    if pool.autoscaling_enabled:
                        result += f"  Autoscaling: {pool.min_node_count} to {pool.max_node_count} nodes\n"
                    
                    if pool.kubernetes_labels:
                        result += "  Kubernetes Labels:\n"
                        for k, v in pool.kubernetes_labels.items():
                            result += f"    {k}: {v}\n"
                    
                    if pool.network_tags:
                        result += f"  Network Tags: {', '.join(pool.network_tags)}\n"
                    
                    if pool.taints:
                        result += "  Taints:\n"
                        for taint in pool.taints:
                            result += f"    {taint.key}={taint.value}:{taint.effect}\n"
                    
                    result += "\n"
                
                return result
            except Exception as e:
                logger.error(f"Error listing node pools: {e}")
                return f"Failed to list node pools in GKE cluster '{cluster_name}' in {location}: {str(e)}"
        
        # Create node pool tool
        @self.mcp.tool()
        async def create_gke_node_pool(
            cluster_name: str,
            location: str,
            node_pool_name: str,
            machine_type: str = "e2-standard-2",
            node_count: int = 3,
            disk_size_gb: int = 100,
            disk_type: Literal["pd-standard", "pd-balanced", "pd-ssd"] = "pd-standard",
            max_pods_per_node: int = 110,
            autoscaling_enabled: bool = False,
            min_node_count: Optional[int] = None,
            max_node_count: Optional[int] = None,
            network_tags: Optional[List[str]] = None,
            kubernetes_labels: Optional[Dict[str, str]] = None,
            labels: Optional[Dict[str, str]] = None,
            taints: Optional[List[Dict[str, str]]] = None
        ) -> str:
            """
            Create a new node pool in an existing GKE cluster.
            
            Args:
                cluster_name: The name of the cluster
                location: The zone or region where the cluster is located
                node_pool_name: Name for the new node pool
                machine_type: Machine type for nodes (e.g. "e2-standard-2")
                node_count: Number of nodes to create
                disk_size_gb: Size of the boot disk in GB
                disk_type: Type of disk to use (standard, balanced, or SSD)
                max_pods_per_node: Maximum number of pods per node
                autoscaling_enabled: Whether to enable autoscaling
                min_node_count: Minimum number of nodes for autoscaling
                max_node_count: Maximum number of nodes for autoscaling
                network_tags: List of network tags to apply to nodes
                kubernetes_labels: Key-value pairs of Kubernetes labels to apply to nodes
                labels: Key-value pairs of GCP labels to apply to the node pool
                taints: List of Kubernetes taints to apply to nodes (format: [{"key": "key1", "value": "value1", "effect": "NO_SCHEDULE"}])
            """
            try:
                # Check if cluster exists
                cluster = self.gke_service.get_cluster(cluster_name, location)
                if not cluster:
                    return f"GKE cluster '{cluster_name}' not found in location {location}."
                
                if cluster.autopilot:
                    return f"Cluster '{cluster_name}' is an Autopilot cluster, which does not support adding custom node pools."
                
                # Validate autoscaling settings
                if autoscaling_enabled:
                    if min_node_count is None or max_node_count is None:
                        return "When autoscaling is enabled, both min_node_count and max_node_count must be specified."
                    if min_node_count >= max_node_count:
                        return "min_node_count must be less than max_node_count."
                
                # Process taints if provided
                node_taints = []
                if taints:
                    for taint in taints:
                        if "key" not in taint or "value" not in taint:
                            return "Each taint must have at least a 'key' and 'value'."
                        effect = taint.get("effect", "NO_SCHEDULE")
                        node_taints.append(NodeTaint(
                            key=taint["key"],
                            value=taint["value"],
                            effect=effect
                        ))
                
                # Create node pool object
                node_pool = NodePool(
                    name=node_pool_name,
                    node_count=node_count,
                    machine_type=machine_type,
                    disk_size_gb=disk_size_gb,
                    disk_type=disk_type,
                    max_pods_per_node=max_pods_per_node,
                    network_tags=network_tags or [],
                    kubernetes_labels=kubernetes_labels or {},
                    labels=labels or {},
                    taints=node_taints,
                    autoscaling_enabled=autoscaling_enabled,
                    min_node_count=min_node_count,
                    max_node_count=max_node_count
                )
                
                # Create the node pool
                result = self.gke_service.create_node_pool(cluster_name, location, node_pool)
                
                return f"Creating node pool '{node_pool_name}' in GKE cluster '{cluster_name}'. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error creating node pool: {e}")
                return f"Failed to create node pool '{node_pool_name}' in GKE cluster '{cluster_name}': {str(e)}"
        
        # Delete node pool tool
        @self.mcp.tool()
        async def delete_gke_node_pool(cluster_name: str, location: str, node_pool_name: str) -> str:
            """
            Delete a node pool from a GKE cluster.
            
            Args:
                cluster_name: The name of the cluster
                location: The zone or region where the cluster is located
                node_pool_name: The name of the node pool to delete
            """
            try:
                # Check if cluster exists
                cluster = self.gke_service.get_cluster(cluster_name, location)
                if not cluster:
                    return f"GKE cluster '{cluster_name}' not found in location {location}."
                
                if cluster.autopilot:
                    return f"Cluster '{cluster_name}' is an Autopilot cluster, which does not have user-manageable node pools."
                
                # Check if node pool exists by listing node pools
                node_pools = self.gke_service.list_node_pools(cluster_name, location)
                node_pool_names = [pool.name for pool in node_pools]
                
                if node_pool_name not in node_pool_names:
                    return f"Node pool '{node_pool_name}' not found in GKE cluster '{cluster_name}'."
                
                # Delete the node pool
                result = self.gke_service.delete_node_pool(cluster_name, location, node_pool_name)
                
                return f"Deleting node pool '{node_pool_name}' from GKE cluster '{cluster_name}'. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error deleting node pool: {e}")
                return f"Failed to delete node pool '{node_pool_name}' from GKE cluster '{cluster_name}': {str(e)}"
        
        # Resize node pool tool
        @self.mcp.tool()
        async def resize_gke_node_pool(cluster_name: str, location: str, node_pool_name: str, node_count: int) -> str:
            """
            Resize a node pool in a GKE cluster.
            
            Args:
                cluster_name: The name of the cluster
                location: The zone or region where the cluster is located
                node_pool_name: The name of the node pool to resize
                node_count: The new number of nodes
            """
            try:
                # Check if cluster exists
                cluster = self.gke_service.get_cluster(cluster_name, location)
                if not cluster:
                    return f"GKE cluster '{cluster_name}' not found in location {location}."
                
                if cluster.autopilot:
                    return f"Cluster '{cluster_name}' is an Autopilot cluster, which does not have user-manageable node pools."
                
                # Check if node pool exists by listing node pools
                node_pools = self.gke_service.list_node_pools(cluster_name, location)
                node_pool_names = [pool.name for pool in node_pools]
                
                if node_pool_name not in node_pool_names:
                    return f"Node pool '{node_pool_name}' not found in GKE cluster '{cluster_name}'."
                
                # Find the node pool to check if autoscaling is enabled
                node_pool = next((pool for pool in node_pools if pool.name == node_pool_name), None)
                if node_pool and node_pool.autoscaling_enabled:
                    return f"Node pool '{node_pool_name}' has autoscaling enabled. To resize, disable autoscaling first."
                
                # Resize the node pool
                result = self.gke_service.resize_node_pool(cluster_name, location, node_pool_name, node_count)
                
                return f"Resizing node pool '{node_pool_name}' in GKE cluster '{cluster_name}' to {node_count} nodes. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error resizing node pool: {e}")
                return f"Failed to resize node pool '{node_pool_name}' in GKE cluster '{cluster_name}': {str(e)}"