from typing import Dict, List, Optional, Union, Any

import httpx
from fastapi import FastAPI
from google.oauth2 import service_account
from googleapiclient import discovery
from mcp.server.fastmcp import FastMCP
from mcp.types import Request, Result
from pydantic import BaseModel, Field
from src.models.models import GCPInstance, GCPInstanceList, GCPOperationResult
from src.server.config import logger
class GCPService:
    """
    Service for interacting with GCP Compute Engine API.
    Handles authentication and provides methods for managing instances.
    """
    
    def __init__(self, project_id: str, credentials_path: str):
        """Initialize the GCP service with project ID and credentials."""
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        
        self.project_id = project_id
        self.credentials_path = credentials_path
        self.compute_service = None
        
    def initialize(self):
        """Initialize the compute service with credentials."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            self.compute_service = discovery.build('compute', 'v1', credentials=credentials)
            logger.info(f"GCP service initialized for project: {self.project_id}")
        except Exception as e:
            logger.error(f"Failed to initialize GCP service: {e}")
            raise
    def list_instances(self, zone: str, page_token: Optional[str] = None) -> GCPInstanceList:
        """
        List all instances in the specified zone.
        
        Args:
            zone: The zone to list instances from
            page_token: Token for pagination
            
        Returns:
            GCPInstanceList: List of instances and next page token if any
        """
        try:
            result = self.compute_service.instances().list(
                project=self.project_id,
                zone=zone,
                pageToken=page_token
            ).execute()
            
            instances = []
            for item in result.get('items', []):
                # Extract network interfaces
                network_interfaces = []
                for ni in item.get('networkInterfaces', []):
                    network_interface = {
                        'network': ni.get('network', ''),
                        'networkIP': ni.get('networkIP', ''),
                        'accessConfigs': ni.get('accessConfigs', [])
                    }
                    network_interfaces.append(network_interface)
                
                # Extract disks
                disks = []
                for disk in item.get('disks', []):
                    disk_info = {
                        'boot': disk.get('boot', False),
                        'autoDelete': disk.get('autoDelete', False),
                        'source': disk.get('source', '')
                    }
                    disks.append(disk_info)
                
                instance = GCPInstance(
                    name=item.get('name', ''),
                    machine_type=item.get('machineType', '').split('/')[-1],
                    zone=zone,
                    status=item.get('status', ''),
                    network_interfaces=network_interfaces,
                    disks=disks,
                    metadata=item.get('metadata', {}),
                    labels=item.get('labels', {})
                )
                instances.append(instance)
            
            return GCPInstanceList(
                instances=instances,
                next_page_token=result.get('nextPageToken')
            )
        except Exception as e:
            logger.error(f"Error listing instances in zone {zone}: {e}")
            raise
    
    def get_instance(self, zone: str, name: str) -> Optional[GCPInstance]:
        """
        Get a specific instance by name in the specified zone.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance
            
        Returns:
            GCPInstance: The instance if found, None otherwise
        """
        try:
            instance = self.compute_service.instances().get(
                project=self.project_id,
                zone=zone,
                instance=name
            ).execute()
            
            # Extract network interfaces
            network_interfaces = []
            for ni in instance.get('networkInterfaces', []):
                network_interface = {
                    'network': ni.get('network', ''),
                    'networkIP': ni.get('networkIP', ''),
                    'accessConfigs': ni.get('accessConfigs', [])
                }
                network_interfaces.append(network_interface)
            
            # Extract disks
            disks = []
            for disk in instance.get('disks', []):
                disk_info = {
                    'boot': disk.get('boot', False),
                    'autoDelete': disk.get('autoDelete', False),
                    'source': disk.get('source', '')
                }
                disks.append(disk_info)
            
            return GCPInstance(
                name=instance.get('name', ''),
                machine_type=instance.get('machineType', '').split('/')[-1],
                zone=zone,
                status=instance.get('status', ''),
                network_interfaces=network_interfaces,
                disks=disks,
                metadata=instance.get('metadata', {}),
                labels=instance.get('labels', {})
            )
        except Exception as e:
            if "not found" in str(e).lower():
                logger.warning(f"Instance {name} not found in zone {zone}")
                return None
            logger.error(f"Error getting instance {name} in zone {zone}: {e}")
            raise
    
    def create_instance(self, instance: GCPInstance) -> GCPOperationResult:
        """
        Create a new instance in GCP.
        
        Args:
            instance: The GCPInstance object with instance details
            
        Returns:
            GCPOperationResult: The result of the create operation
        """
        # Determine the full machine type URL
        machine_type_url = f"zones/{instance.zone}/machineTypes/{instance.machine_type}"
        
        # Build the instance configuration
        config = {
            'name': instance.name,
            'machineType': machine_type_url,
            'networkInterfaces': instance.network_interfaces or [{
                'network': f'global/networks/default',
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],
            'disks': instance.disks or [{
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': instance.source_image
                }
            }],
            'metadata': {
                'items': [
                    {'key': k, 'value': v} for k, v in instance.metadata.items()
                ]
            },
            'labels': instance.labels
        }
        
        try:
            operation = self.compute_service.instances().insert(
                project=self.project_id,
                zone=instance.zone,
                body=config
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='create',
                target_id=operation.get('targetId')
            )
        except Exception as e:
            logger.error(f"Error creating instance {instance.name}: {e}")
            raise
    
    def delete_instance(self, zone: str, name: str) -> GCPOperationResult:
        """
        Delete an instance from GCP.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance to delete
            
        Returns:
            GCPOperationResult: The result of the delete operation
        """
        try:
            operation = self.compute_service.instances().delete(
                project=self.project_id,
                zone=zone,
                instance=name
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='delete',
                target_id=operation.get('targetId')
            )
        except Exception as e:
            logger.error(f"Error deleting instance {name}: {e}")
            raise
    
    def modify_instance(self, zone: str, name: str, labels: Dict[str, str] = None, 
                       metadata: Dict[str, str] = None) -> GCPOperationResult:
        """
        Modify an existing instance (labels and/or metadata).
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance to modify
            labels: New labels to set
            metadata: New metadata to set
            
        Returns:
            GCPOperationResult: The result of the modify operation
        """
        try:
            # Get the fingerprint of the instance for optimistic locking
            instance = self.compute_service.instances().get(
                project=self.project_id,
                zone=zone,
                instance=name
            ).execute()
            
            # Update labels if provided
            if labels is not None:
                label_req = self.compute_service.instances().setLabels(
                    project=self.project_id,
                    zone=zone,
                    instance=name,
                    body={
                        'labels': labels,
                        'labelFingerprint': instance.get('labelFingerprint', '')
                    }
                ).execute()
            
            # Update metadata if provided
            if metadata is not None:
                metadata_items = [{'key': k, 'value': v} for k, v in metadata.items()]
                metadata_req = self.compute_service.instances().setMetadata(
                    project=self.project_id,
                    zone=zone,
                    instance=name,
                    body={
                        'items': metadata_items,
                        'fingerprint': instance.get('metadata', {}).get('fingerprint', '')
                    }
                ).execute()
            
            # Return the operation result
            operation = label_req if labels is not None else metadata_req
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='modify',
                target_id=operation.get('targetId')
            )
        except Exception as e:
            logger.error(f"Error modifying instance {name}: {e}")
            raise
    
    def stop_instance(self, zone: str, name: str) -> GCPOperationResult:
        """
        Stop a running instance.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance to stop
            
        Returns:
            GCPOperationResult: The result of the stop operation
        """
        try:
            operation = self.compute_service.instances().stop(
                project=self.project_id,
                zone=zone,
                instance=name
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='stop',
                target_id=operation.get('targetId')
            )
        except Exception as e:
            logger.error(f"Error stopping instance {name}: {e}")
            raise
    
    def start_instance(self, zone: str, name: str) -> GCPOperationResult:
        """
        Start a stopped instance.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance to start
            
        Returns:
            GCPOperationResult: The result of the start operation
        """
        try:
            operation = self.compute_service.instances().start(
                project=self.project_id,
                zone=zone,
                instance=name
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='start',
                target_id=operation.get('targetId')
            )
        except Exception as e:
            logger.error(f"Error starting instance {name}: {e}")
            raise