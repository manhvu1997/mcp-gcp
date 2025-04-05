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
import time

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
    
    def modify_instance(self, zone: str, name: str, 
                       machine_type: Optional[str] = None,
                       network_interfaces: Optional[List[Dict[str, Any]]] = None,
                       disks: Optional[List[Dict[str, Any]]] = None,
                       labels: Optional[Dict[str, str]] = None,
                       metadata: Optional[Dict[str, str]] = None) -> GCPOperationResult:
        """
        Modify an existing instance with comprehensive changes.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance to modify
            machine_type: New machine type to set
            network_interfaces: New network interfaces configuration
            disks: New disks configuration
            labels: New labels to set
            metadata: New metadata to set
            
        Returns:
            GCPOperationResult: The result of the modify operation
        """
        try:
            # Get the current instance configuration
            instance = self.compute_service.instances().get(
                project=self.project_id,
                zone=zone,
                instance=name
            ).execute()
            
            # Prepare the instance configuration for update
            config = {}
            
            # Update machine type if provided
            if machine_type is not None:
                config['machineType'] = f"zones/{zone}/machineTypes/{machine_type}"
            
            # Update network interfaces if provided
            if network_interfaces is not None:
                config['networkInterfaces'] = network_interfaces
            
            # Update disks if provided
            if disks is not None:
                config['disks'] = disks
            
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
            
            # If there are configuration changes, update the instance
            if config:
                # Create a new instance configuration that preserves existing fields
                update_config = {
                    'name': name,
                    'machineType': config.get('machineType', instance.get('machineType')),
                    'networkInterfaces': config.get('networkInterfaces', instance.get('networkInterfaces')),
                    'disks': config.get('disks', instance.get('disks')),
                    'metadata': instance.get('metadata', {}),
                    'labels': instance.get('labels', {})
                }
                
                # Remove any None values to prevent API errors
                update_config = {k: v for k, v in update_config.items() if v is not None}
                
                operation = self.compute_service.instances().update(
                    project=self.project_id,
                    zone=zone,
                    instance=name,
                    body=update_config
                ).execute()
                return GCPOperationResult(
                    name=operation.get('name', ''),
                    status=operation.get('status', ''),
                    operation_type='modify',
                    target_id=operation.get('targetId')
                )
            
            # If only labels or metadata were updated, return that operation result
            if labels is not None:
                return GCPOperationResult(
                    name=label_req.get('name', ''),
                    status=label_req.get('status', ''),
                    operation_type='modify_labels',
                    target_id=label_req.get('targetId')
                )
            elif metadata is not None:
                return GCPOperationResult(
                    name=metadata_req.get('name', ''),
                    status=metadata_req.get('status', ''),
                    operation_type='modify_metadata',
                    target_id=metadata_req.get('targetId')
                )
            
            raise ValueError("No modifications specified")
            
        except Exception as e:
            logger.error(f"Error modifying instance {name}: {e}")
            raise

    def modify_instance_with_restart(self, zone: str, name: str,
                                   machine_type: Optional[str] = None,
                                   network_interfaces: Optional[List[Dict[str, Any]]] = None,
                                   disks: Optional[List[Dict[str, Any]]] = None,
                                   labels: Optional[Dict[str, str]] = None,
                                   metadata: Optional[Dict[str, str]] = None) -> List[GCPOperationResult]:
        """
        Modify an instance with a stop-edit-start workflow for changes that require instance restart.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance to modify
            machine_type: New machine type to set
            network_interfaces: New network interfaces configuration
            disks: New disks configuration
            labels: New labels to set
            metadata: New metadata to set
            
        Returns:
            List[GCPOperationResult]: List of operation results for stop, modify, and start operations
        """
        try:
            results = []
            
            # Stop the instance
            stop_result = self.stop_instance(zone, name)
            results.append(stop_result)
            
            # Wait for the instance to stop
            while True:
                instance = self.get_instance(zone, name)
                if instance and instance.status == "TERMINATED":
                    break
                time.sleep(5)  # Wait 5 seconds before checking again
            
            # Modify the instance
            modify_result = self.modify_instance(
                zone=zone,
                name=name,
                machine_type=machine_type,
                network_interfaces=network_interfaces,
                disks=disks,
                labels=labels,
                metadata=metadata
            )
            results.append(modify_result)
            
            # Start the instance
            start_result = self.start_instance(zone, name)
            results.append(start_result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error in stop-edit-start workflow for instance {name}: {e}")
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

    def add_disk(self, zone: str, name: str, disk_config: Dict[str, Any]) -> GCPOperationResult:
        """
        Add a new disk to an existing instance.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance
            disk_config: Configuration for the new disk, including:
                - name: Name of the disk
                - size_gb: Size in GB
                - disk_type: Type of disk (e.g., pd-standard, pd-ssd)
                - auto_delete: Whether to auto-delete when instance is deleted
                - mode: Mode of attachment (READ_WRITE or READ_ONLY)
                
        Returns:
            GCPOperationResult: The result of the add disk operation
        """
        try:
            # Get the current instance configuration
            instance = self.compute_service.instances().get(
                project=self.project_id,
                zone=zone,
                instance=name
            ).execute()
            
            # Prepare the disk configuration
            disk_name = disk_config.get('name')
            disk_type = disk_config.get('disk_type', 'pd-standard')
            size_gb = disk_config.get('size_gb', 10)
            auto_delete = disk_config.get('auto_delete', True)
            mode = disk_config.get('mode', 'READ_WRITE')
            
            # Create the disk
            disk_body = {
                'name': disk_name,
                'sizeGb': size_gb,
                'type': f"zones/{zone}/diskTypes/{disk_type}",
                'autoDelete': auto_delete
            }
            
            # Create the disk first
            disk_operation = self.compute_service.disks().insert(
                project=self.project_id,
                zone=zone,
                body=disk_body
            ).execute()
            
            # Wait for disk creation to complete
            while True:
                disk = self.compute_service.disks().get(
                    project=self.project_id,
                    zone=zone,
                    disk=disk_name
                ).execute()
                if disk.get('status') == 'READY':
                    break
                time.sleep(5)
            
            # Attach the disk to the instance
            attach_body = {
                'source': f"projects/{self.project_id}/zones/{zone}/disks/{disk_name}",
                'autoDelete': auto_delete,
                'mode': mode
            }
            
            operation = self.compute_service.instances().attachDisk(
                project=self.project_id,
                zone=zone,
                instance=name,
                body=attach_body
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='add_disk',
                target_id=operation.get('targetId')
            )
            
        except Exception as e:
            logger.error(f"Error adding disk to instance {name}: {e}")
            raise

    def modify_disk(self, zone: str, name: str, disk_name: str, 
                   size_gb: Optional[int] = None,
                   disk_type: Optional[str] = None) -> GCPOperationResult:
        """
        Modify an existing disk attached to an instance.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance
            disk_name: The name of the disk to modify
            size_gb: New size in GB
            disk_type: New disk type (e.g., pd-standard, pd-ssd)
            
        Returns:
            GCPOperationResult: The result of the modify disk operation
        """
        try:
            # Get the current disk configuration
            disk = self.compute_service.disks().get(
                project=self.project_id,
                zone=zone,
                disk=disk_name
            ).execute()
            
            # Prepare the update configuration
            update_config = {}
            
            if size_gb is not None:
                update_config['sizeGb'] = size_gb
            
            if disk_type is not None:
                update_config['type'] = f"zones/{zone}/diskTypes/{disk_type}"
            
            if not update_config:
                raise ValueError("No modifications specified for disk")
            
            # Update the disk
            operation = self.compute_service.disks().update(
                project=self.project_id,
                zone=zone,
                disk=disk_name,
                body=update_config
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='modify_disk',
                target_id=operation.get('targetId')
            )
            
        except Exception as e:
            logger.error(f"Error modifying disk {disk_name} on instance {name}: {e}")
            raise

    def attach_disk(self, zone: str, name: str, disk_name: str,
                   auto_delete: bool = True,
                   mode: str = 'READ_WRITE') -> GCPOperationResult:
        """
        Attach an existing disk to an instance.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance
            disk_name: The name of the disk to attach
            auto_delete: Whether to auto-delete when instance is deleted
            mode: Mode of attachment (READ_WRITE or READ_ONLY)
            
        Returns:
            GCPOperationResult: The result of the attach disk operation
        """
        try:
            # Check if disk exists
            disk = self.compute_service.disks().get(
                project=self.project_id,
                zone=zone,
                disk=disk_name
            ).execute()
            
            if not disk:
                raise ValueError(f"Disk {disk_name} not found in zone {zone}")
            
            # Attach the disk
            attach_body = {
                'source': f"projects/{self.project_id}/zones/{zone}/disks/{disk_name}",
                'autoDelete': auto_delete,
                'mode': mode
            }
            
            operation = self.compute_service.instances().attachDisk(
                project=self.project_id,
                zone=zone,
                instance=name,
                body=attach_body
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='attach_disk',
                target_id=operation.get('targetId')
            )
            
        except Exception as e:
            logger.error(f"Error attaching disk {disk_name} to instance {name}: {e}")
            raise

    def detach_disk(self, zone: str, name: str, device_name: str) -> GCPOperationResult:
        """
        Detach a disk from an instance.
        
        Args:
            zone: The zone where the instance is located
            name: The name of the instance
            device_name: The device name of the disk to detach
            
        Returns:
            GCPOperationResult: The result of the detach disk operation
        """
        try:
            operation = self.compute_service.instances().detachDisk(
                project=self.project_id,
                zone=zone,
                instance=name,
                deviceName=device_name
            ).execute()
            
            return GCPOperationResult(
                name=operation.get('name', ''),
                status=operation.get('status', ''),
                operation_type='detach_disk',
                target_id=operation.get('targetId')
            )
            
        except Exception as e:
            logger.error(f"Error detaching disk {device_name} from instance {name}: {e}")
            raise