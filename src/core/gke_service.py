"""
GKE Service implementation for cluster and nodepool management.
"""
import logging
from typing import Dict, List, Optional, Any, Union

from google.oauth2 import service_account
from googleapiclient import discovery

from src.models.gke_models import GKECluster, NodePool, GKEOperation, NodeTaint

logger = logging.getLogger(__name__)

class GKEService:
    """
    Service for interacting with GKE API.
    Handles authentication and provides methods for managing GKE clusters and nodepools.
    """
    
    def __init__(self, project_id: str, credentials_path: str):
        """Initialize the GKE service with project ID and credentials."""
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.container_service = None
        
    def initialize(self):
        """Initialize the container service with credentials."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            self.container_service = discovery.build('container', 'v1', credentials=credentials)
            logger.info(f"GKE service initialized for project: {self.project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize GKE service: {e}")
            raise
    
    def list_clusters(self, location: Optional[str] = None) -> List[GKECluster]:
        """
        List all GKE clusters in the specified location or across all locations.
        
        Args:
            location: The zone or region to list clusters from (optional)
            
        Returns:
            List[GKECluster]: List of GKE clusters
        """
        try:
            if location:
                # Check if location is a zone or region
                if '-' in location.split('-')[-1]:  # e.g., us-central1-a
                    result = self.container_service.projects().zones().clusters().list(
                        projectId=self.project_id,
                        zone=location
                    ).execute()
                else:  # region
                    result = self.container_service.projects().locations().clusters().list(
                        parent=f"projects/{self.project_id}/locations/{location}"
                    ).execute()
            else:
                # List clusters across all locations
                result = self.container_service.projects().aggregated().clusters().list(
                    parent=f"projects/{self.project_id}"
                ).execute()
            
            clusters = []
            
            # Process the result based on which API was used
            if 'clusters' in result:
                for item in result.get('clusters', []):
                    cluster = self._cluster_dict_to_model(item)
                    clusters.append(cluster)
            
            return clusters
        except Exception as e:
            logger.error(f"Error listing GKE clusters in location {location}: {e}")
            raise
    
    def get_cluster(self, name: str, location: str) -> Optional[GKECluster]:
        """
        Get a specific GKE cluster by name in the specified location.
        
        Args:
            name: The name of the cluster
            location: The zone or region where the cluster is located
            
        Returns:
            GKECluster: The cluster if found, None otherwise
        """
        try:
            # Check if location is a zone or region
            if '-' in location.split('-')[-1]:  # e.g., us-central1-a
                result = self.container_service.projects().zones().clusters().get(
                    projectId=self.project_id,
                    zone=location,
                    clusterId=name
                ).execute()
            else:  # region
                result = self.container_service.projects().locations().clusters().get(
                    name=f"projects/{self.project_id}/locations/{location}/clusters/{name}"
                ).execute()
            
            return self._cluster_dict_to_model(result)
        except Exception as e:
            if "not found" in str(e).lower():
                logger.warning(f"Cluster {name} not found in location {location}")
                return None
            logger.error(f"Error getting cluster {name} in location {location}: {e}")
            raise
    
    def create_cluster(self, cluster: GKECluster) -> GKEOperation:
        """
        Create a new GKE cluster.
        
        Args:
            cluster: The GKECluster object with cluster details
            
        Returns:
            GKEOperation: The result of the create operation
        """
        try:
            # Build the cluster configuration
            cluster_config = self._build_cluster_config(cluster)
            
            # Choose the appropriate API based on location type
            if cluster.is_regional:
                operation = self.container_service.projects().locations().clusters().create(
                    parent=f"projects/{self.project_id}/locations/{cluster.location}",
                    body=cluster_config
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='create',
                    target_id=cluster.name,
                    region=cluster.location
                )
            else:
                operation = self.container_service.projects().zones().clusters().create(
                    projectId=self.project_id,
                    zone=cluster.location,
                    body=cluster_config
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='create',
                    target_id=cluster.name,
                    zone=cluster.location
                )
        except Exception as e:
            logger.error(f"Error creating cluster {cluster.name}: {e}")
            raise
    
    def delete_cluster(self, name: str, location: str) -> GKEOperation:
        """
        Delete a GKE cluster.
        
        Args:
            name: The name of the cluster to delete
            location: The zone or region where the cluster is located
            
        Returns:
            GKEOperation: The result of the delete operation
        """
        try:
            # Check if location is a zone or region
            if '-' in location.split('-')[-1]:  # e.g., us-central1-a
                operation = self.container_service.projects().zones().clusters().delete(
                    projectId=self.project_id,
                    zone=location,
                    clusterId=name
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='delete',
                    target_id=name,
                    zone=location
                )
            else:  # region
                operation = self.container_service.projects().locations().clusters().delete(
                    name=f"projects/{self.project_id}/locations/{location}/clusters/{name}"
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='delete',
                    target_id=name,
                    region=location
                )
        except Exception as e:
            logger.error(f"Error deleting cluster {name}: {e}")
            raise
    
    def list_node_pools(self, cluster_name: str, location: str) -> List[NodePool]:
        """
        List all node pools in a specific GKE cluster.
        
        Args:
            cluster_name: The name of the cluster
            location: The zone or region where the cluster is located
            
        Returns:
            List[NodePool]: List of node pools in the cluster
        """
        try:
            # Check if location is a zone or region
            if '-' in location.split('-')[-1]:  # e.g., us-central1-a
                result = self.container_service.projects().zones().clusters().nodePools().list(
                    projectId=self.project_id,
                    zone=location,
                    clusterId=cluster_name
                ).execute()
            else:  # region
                result = self.container_service.projects().locations().clusters().nodePools().list(
                    parent=f"projects/{self.project_id}/locations/{location}/clusters/{cluster_name}"
                ).execute()
            
            node_pools = []
            for item in result.get('nodePools', []):
                node_pool = self._node_pool_dict_to_model(item)
                node_pools.append(node_pool)
            
            return node_pools
        except Exception as e:
            logger.error(f"Error listing node pools for cluster {cluster_name} in location {location}: {e}")
            raise
    
    def create_node_pool(self, cluster_name: str, location: str, node_pool: NodePool) -> GKEOperation:
        """
        Create a new node pool in an existing GKE cluster.
        
        Args:
            cluster_name: The name of the cluster
            location: The zone or region where the cluster is located
            node_pool: The NodePool object with node pool details
            
        Returns:
            GKEOperation: The result of the create operation
        """
        try:
            # Build the node pool configuration
            node_pool_config = self._build_node_pool_config(node_pool)
            
            # Choose the appropriate API based on location type
            if '-' in location.split('-')[-1]:  # e.g., us-central1-a
                operation = self.container_service.projects().zones().clusters().nodePools().create(
                    projectId=self.project_id,
                    zone=location,
                    clusterId=cluster_name,
                    body=node_pool_config
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='create_node_pool',
                    target_id=node_pool.name,
                    zone=location
                )
            else:  # region
                operation = self.container_service.projects().locations().clusters().nodePools().create(
                    parent=f"projects/{self.project_id}/locations/{location}/clusters/{cluster_name}",
                    body=node_pool_config
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='create_node_pool',
                    target_id=node_pool.name,
                    region=location
                )
        except Exception as e:
            logger.error(f"Error creating node pool {node_pool.name} in cluster {cluster_name}: {e}")
            raise
    
    def delete_node_pool(self, cluster_name: str, location: str, node_pool_name: str) -> GKEOperation:
        """
        Delete a node pool from a GKE cluster.
        
        Args:
            cluster_name: The name of the cluster
            location: The zone or region where the cluster is located
            node_pool_name: The name of the node pool to delete
            
        Returns:
            GKEOperation: The result of the delete operation
        """
        try:
            # Check if location is a zone or region
            if '-' in location.split('-')[-1]:  # e.g., us-central1-a
                operation = self.container_service.projects().zones().clusters().nodePools().delete(
                    projectId=self.project_id,
                    zone=location,
                    clusterId=cluster_name,
                    nodePoolId=node_pool_name
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='delete_node_pool',
                    target_id=node_pool_name,
                    zone=location
                )
            else:  # region
                operation = self.container_service.projects().locations().clusters().nodePools().delete(
                    name=f"projects/{self.project_id}/locations/{location}/clusters/{cluster_name}/nodePools/{node_pool_name}"
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='delete_node_pool',
                    target_id=node_pool_name,
                    region=location
                )
        except Exception as e:
            logger.error(f"Error deleting node pool {node_pool_name} from cluster {cluster_name}: {e}")
            raise
    
    def resize_node_pool(self, cluster_name: str, location: str, node_pool_name: str, node_count: int) -> GKEOperation:
        """
        Resize a node pool in a GKE cluster.
        
        Args:
            cluster_name: The name of the cluster
            location: The zone or region where the cluster is located
            node_pool_name: The name of the node pool to resize
            node_count: The new number of nodes
            
        Returns:
            GKEOperation: The result of the resize operation
        """
        try:
            # Check if location is a zone or region
            if '-' in location.split('-')[-1]:  # e.g., us-central1-a
                operation = self.container_service.projects().zones().clusters().nodePools().setSize(
                    projectId=self.project_id,
                    zone=location,
                    clusterId=cluster_name,
                    nodePoolId=node_pool_name,
                    body={
                        'nodeCount': node_count
                    }
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='resize_node_pool',
                    target_id=node_pool_name,
                    zone=location
                )
            else:  # region
                operation = self.container_service.projects().locations().clusters().nodePools().setSize(
                    name=f"projects/{self.project_id}/locations/{location}/clusters/{cluster_name}/nodePools/{node_pool_name}",
                    body={
                        'nodeCount': node_count
                    }
                ).execute()
                
                return GKEOperation(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='resize_node_pool',
                    target_id=node_pool_name,
                    region=location
                )
        except Exception as e:
            logger.error(f"Error resizing node pool {node_pool_name} in cluster {cluster_name}: {e}")
            raise
    
    def _build_cluster_config(self, cluster: GKECluster) -> Dict[str, Any]:
        """
        Build a cluster configuration dictionary from a GKECluster model.
        
        Args:
            cluster: The GKECluster object
            
        Returns:
            Dict[str, Any]: The cluster configuration dictionary
        """
        config = {
            'name': cluster.name,
        }
        
        # Handle autopilot vs standard mode
        if cluster.autopilot:
            config['autopilot'] = {
                'enabled': True
            }
        else:
            # Add node pools for standard clusters
            config['nodePools'] = [
                self._build_node_pool_config(pool)
                for pool in cluster.node_pools
            ]
        
        # Add networking configuration if specified
        network_config = {}
        
        if cluster.cluster_ipv4_cidr:
            network_config['clusterIpv4Cidr'] = cluster.cluster_ipv4_cidr
        
        if cluster.services_ipv4_cidr:
            network_config['servicesIpv4Cidr'] = cluster.services_ipv4_cidr
        
        if cluster.network:
            network_config['network'] = cluster.network
        
        if cluster.subnetwork:
            network_config['subnetwork'] = cluster.subnetwork
        
        # Configure private cluster if specified
        if cluster.private_cluster:
            network_config['privateClusterConfig'] = {
                'enablePrivateNodes': cluster.enable_private_nodes,
                'enablePrivateEndpoint': cluster.enable_private_endpoint,
                'masterIpv4CidrBlock': cluster.master_ipv4_cidr_block
            }
        
        # Add network configuration to the cluster config if any options were set
        if network_config:
            config['networkConfig'] = network_config
        
        # Add Kubernetes version if specified
        if cluster.kubernetes_version:
            config['initialClusterVersion'] = cluster.kubernetes_version
        
        return config
    
    def _build_node_pool_config(self, node_pool: NodePool) -> Dict[str, Any]:
        """
        Build a node pool configuration dictionary from a NodePool model.
        
        Args:
            node_pool: The NodePool object
            
        Returns:
            Dict[str, Any]: The node pool configuration dictionary
        """
        config = {
            'name': node_pool.name,
            'initialNodeCount': node_pool.node_count,
            'config': {
                'machineType': node_pool.machine_type,
                'diskSizeGb': node_pool.disk_size_gb,
                'diskType': node_pool.disk_type,
                'oauthScopes': [
                    'https://www.googleapis.com/auth/devstorage.read_only',
                    'https://www.googleapis.com/auth/logging.write',
                    'https://www.googleapis.com/auth/monitoring',
                    'https://www.googleapis.com/auth/servicecontrol',
                    'https://www.googleapis.com/auth/service.management.readonly',
                    'https://www.googleapis.com/auth/trace.append'
                ]
            },
            'maxPodsConstraint': {
                'maxPodsPerNode': str(node_pool.max_pods_per_node)
            }
        }
        
        # Add network tags if specified
        if node_pool.network_tags:
            config['config']['tags'] = node_pool.network_tags
        
        # Add Kubernetes labels if specified
        if node_pool.kubernetes_labels:
            config['config']['labels'] = node_pool.kubernetes_labels
        
        # Add resource labels (Google Cloud labels) if specified
        if node_pool.labels:
            config['resourceLabels'] = node_pool.labels
        
        # Add taints if specified
        if node_pool.taints:
            config['config']['taints'] = [
                {
                    'key': taint.key,
                    'value': taint.value,
                    'effect': taint.effect
                }
                for taint in node_pool.taints
            ]
        
        # Add autoscaling configuration if enabled
        if node_pool.autoscaling_enabled and node_pool.min_node_count and node_pool.max_node_count:
            config['autoscaling'] = {
                'enabled': True,
                'minNodeCount': node_pool.min_node_count,
                'maxNodeCount': node_pool.max_node_count
            }
        
        return config
    
    def _cluster_dict_to_model(self, cluster_dict: Dict[str, Any]) -> GKECluster:
        """
        Convert a cluster dictionary from the API to a GKECluster model.
        
        Args:
            cluster_dict: The cluster dictionary
            
        Returns:
            GKECluster: The cluster model
        """
        # Determine location and location type
        location = cluster_dict.get('location', '')
        location_type = 'regional' if location and not location.endswith('-a') else 'zonal'
        
        # Extract network configuration
        network_config = cluster_dict.get('networkConfig', {})
        private_cluster_config = cluster_dict.get('privateClusterConfig', {})
        
        # Determine if autopilot is enabled
        autopilot = cluster_dict.get('autopilot', {}).get('enabled', False)
        
        # Extract node pools
        node_pools = []
        for np in cluster_dict.get('nodePools', []):
            node_pool = self._node_pool_dict_to_model(np)
            node_pools.append(node_pool)
        
        # Create and return the GKECluster model
        return GKECluster(
            name=cluster_dict.get('name', ''),
            location=location,
            location_type=location_type,
            autopilot=autopilot,
            node_pools=node_pools,
            cluster_ipv4_cidr=network_config.get('clusterIpv4Cidr'),
            services_ipv4_cidr=network_config.get('servicesIpv4Cidr'),
            private_cluster=bool(private_cluster_config),
            network=network_config.get('network'),
            subnetwork=network_config.get('subnetwork'),
            enable_private_nodes=private_cluster_config.get('enablePrivateNodes', False),
            enable_private_endpoint=private_cluster_config.get('enablePrivateEndpoint', False),
            master_ipv4_cidr_block=private_cluster_config.get('masterIpv4CidrBlock'),
            kubernetes_version=cluster_dict.get('currentMasterVersion')
        )
    
    def _node_pool_dict_to_model(self, node_pool_dict: Dict[str, Any]) -> NodePool:
        """
        Convert a node pool dictionary from the API to a NodePool model.
        
        Args:
            node_pool_dict: The node pool dictionary
            
        Returns:
            NodePool: The node pool model
        """
        # Extract node config
        config = node_pool_dict.get('config', {})
        
        # Extract autoscaling config
        autoscaling = node_pool_dict.get('autoscaling', {})
        autoscaling_enabled = autoscaling.get('enabled', False)
        
        # Extract taints
        taints = []
        for taint_dict in config.get('taints', []):
            taints.append(NodeTaint(
                key=taint_dict.get('key', ''),
                value=taint_dict.get('value', ''),
                effect=taint_dict.get('effect', 'NO_SCHEDULE')
            ))
        
        # Create and return the NodePool model
        return NodePool(
            name=node_pool_dict.get('name', ''),
            node_count=node_pool_dict.get('initialNodeCount', 0),
            machine_type=config.get('machineType', 'e2-standard-2'),
            disk_size_gb=config.get('diskSizeGb', 100),
            disk_type=config.get('diskType', 'pd-standard'),
            max_pods_per_node=int(node_pool_dict.get('maxPodsConstraint', {}).get('maxPodsPerNode', 110)),
            network_tags=config.get('tags', []),
            kubernetes_labels=config.get('labels', {}),
            labels=node_pool_dict.get('resourceLabels', {}),
            taints=taints,
            autoscaling_enabled=autoscaling_enabled,
            min_node_count=autoscaling.get('minNodeCount') if autoscaling_enabled else None,
            max_node_count=autoscaling.get('maxNodeCount') if autoscaling_enabled else None
        )