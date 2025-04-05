"""
MCP Tools for GCP instance management.
This module defines functions that are registered as MCP tools.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any

from src.core.instance import GCPService
from src.models.models import GCPInstance

logger = logging.getLogger(__name__)

class GCPTools:
    """
    Collection of GCP instance management tools for MCP.
    """
    
    def __init__(self, gcp_service: GCPService, mcp):
        """
        Initialize with a GCP service and MCP instance.
        
        Args:
            gcp_service: GCP service instance
            mcp: MCP instance for registering tools
        """
        self.gcp_service = gcp_service
        self.mcp = mcp
        self.register_tools()
    
    def register_tools(self):
        """Register all tools with MCP."""
        # List instances tool
        @self.mcp.tool()
        async def list_instances(zone: str) -> str:
            """
            List all GCP instances in the specified zone.
            
            Args:
                zone: The zone to list instances from (e.g., us-central1-a)
            """
            try:
                instance_list = self.gcp_service.list_instances(zone)
                
                if not instance_list.instances:
                    return f"No instances found in zone {zone}."
                
                # Format the response
                result = f"Instances in zone {zone}:\n\n"
                for instance in instance_list.instances:
                    result += f"- {instance.name} ({instance.machine_type}): {instance.status}\n"
                
                return result
            except Exception as e:
                logger.error(f"Error listing instances: {e}")
                return f"Failed to list instances in zone {zone}: {str(e)}"
        
        # Get instance details tool
        @self.mcp.tool()
        async def get_instance(name: str, zone: str) -> str:
            """
            Get details for a specific GCP instance.
            
            Args:
                name: The name of the instance
                zone: The zone where the instance is located
            """
            try:
                instance = self.gcp_service.get_instance(zone, name)
                
                if not instance:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Format the response
                result = f"Instance Details: {instance.name}\n"
                result += f"  Zone: {zone}\n"
                result += f"  Machine Type: {instance.machine_type}\n"
                result += f"  Status: {instance.status}\n"
                
                # Add network information
                if instance.network_interfaces:
                    result += "  Network Interfaces:\n"
                    for ni in instance.network_interfaces:
                        result += f"    - Network: {ni.get('network', '').split('/')[-1]}\n"
                        result += f"      IP: {ni.get('networkIP', '')}\n"
                        
                        # Add access configs (external IPs)
                        for ac in ni.get('accessConfigs', []):
                            if 'natIP' in ac:
                                result += f"      External IP: {ac.get('natIP', '')}\n"
                
                # Add disk information
                if instance.disks:
                    result += "  Disks:\n"
                    for disk in instance.disks:
                        disk_name = disk.get('source', '').split('/')[-1]
                        result += f"    - {disk_name} (Boot: {disk.get('boot', False)})\n"
                
                # Add labels if present
                if instance.labels:
                    result += "  Labels:\n"
                    for k, v in instance.labels.items():
                        result += f"    - {k}: {v}\n"
                
                # Add metadata if present
                if instance.metadata and 'items' in instance.metadata:
                    result += "  Metadata:\n"
                    for item in instance.metadata.get('items', []):
                        result += f"    - {item.get('key')}: {item.get('value')}\n"
                
                return result
            except Exception as e:
                logger.error(f"Error getting instance details: {e}")
                return f"Failed to get details for instance '{name}' in zone {zone}: {str(e)}"
        
        # Create instance tool
        @self.mcp.tool()
        async def create_instance(
            name: str, 
            zone: str,
            machine_type: str = "n1-standard-1",
            labels: Optional[Dict[str, str]] = None,
            source_image: str = "projects/debian-cloud/global/images/family/debian-10",
            network_interfaces: Optional[List[Dict[str, Any]]] = None,
            disks: Optional[List[Dict[str, Any]]] = None,
            metadata: Optional[Dict[str, str]] = None
        ) -> str:
            """
            Create a new GCP instance.
            
            Args:
                name: Name for the new instance
                zone: Zone to create the instance in
                machine_type: Machine type (e.g., n1-standard-1)
                labels: Labels to attach to the instance (e.g., {"env": "prod", "project": "demo"})
                source_image: Source image to use for the instance (e.g., "projects/debian-cloud/global/images/family/debian-10")
                network_interfaces: Network interfaces configuration
                disks: Disks configuration
                metadata: Metadata configuration
            """
            try:
                # Handle None values
                labels = labels or {}
                
                # Create instance object
                instance = GCPInstance(
                    name=name,
                    machine_type=machine_type,
                    zone=zone,
                    labels=labels,
                    source_image=source_image,
                    network_interfaces=network_interfaces,
                    disks=disks,
                    metadata=metadata
                )
                
                # Check if instance already exists
                existing = self.gcp_service.get_instance(zone, name)
                if existing:
                    return f"Instance '{name}' already exists in zone {zone}."
                
                # Create the instance
                result = self.gcp_service.create_instance(instance)
                
                return f"Creating instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error creating instance: {e}")
                return f"Failed to create instance '{name}' in zone {zone}: {str(e)}"
        
        # Delete instance tool
        @self.mcp.tool()
        async def delete_instance(name: str, zone: str) -> str:
            """
            Delete a GCP instance.
            
            Args:
                name: Name of the instance to delete
                zone: Zone where the instance is located
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Delete the instance
                result = self.gcp_service.delete_instance(zone, name)
                
                return f"Deleting instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error deleting instance: {e}")
                return f"Failed to delete instance '{name}' in zone {zone}: {str(e)}"
        
        # Start instance tool
        @self.mcp.tool()
        async def start_instance(name: str, zone: str) -> str:
            """
            Start a GCP instance.
            
            Args:
                name: Name of the instance to start
                zone: Zone where the instance is located
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Check if instance is already running
                if existing.status == "RUNNING":
                    return f"Instance '{name}' is already running."
                
                # Start the instance
                result = self.gcp_service.start_instance(zone, name)
                
                return f"Starting instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error starting instance: {e}")
                return f"Failed to start instance '{name}' in zone {zone}: {str(e)}"
        
        # Stop instance tool
        @self.mcp.tool()
        async def stop_instance(name: str, zone: str) -> str:
            """
            Stop a GCP instance.
            
            Args:
                name: Name of the instance to stop
                zone: Zone where the instance is located
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Check if instance is already stopped
                if existing.status == "TERMINATED":
                    return f"Instance '{name}' is already stopped."
                
                # Stop the instance
                result = self.gcp_service.stop_instance(zone, name)
                
                return f"Stopping instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error stopping instance: {e}")
                return f"Failed to stop instance '{name}' in zone {zone}: {str(e)}"
        
        # Modify instance tool
        @self.mcp.tool()
        async def modify_instance(
            name: str,
            zone: str,
            machine_type: Optional[str] = None,
            network_interfaces: Optional[List[Dict[str, Any]]] = None,
            disks: Optional[List[Dict[str, Any]]] = None,
            labels: Optional[Dict[str, str]] = None,
            metadata: Optional[Dict[str, str]] = None
        ) -> str:
            """
            Modify a GCP instance with comprehensive changes.
            
            Args:
                name: Name of the instance to modify
                zone: Zone where the instance is located
                machine_type: New machine type to set (e.g., n2-standard-4)
                network_interfaces: New network interfaces configuration
                disks: New disks configuration
                labels: New labels to set
                metadata: New metadata to set
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Modify the instance
                result = self.gcp_service.modify_instance(
                    zone=zone,
                    name=name,
                    machine_type=machine_type,
                    network_interfaces=network_interfaces,
                    disks=disks,
                    labels=labels,
                    metadata=metadata
                )
                
                # Format response
                result_str = f"Modifying instance '{name}' in zone {zone}.\n"
                if machine_type:
                    result_str += f"  - Machine Type: {machine_type}\n"
                if network_interfaces:
                    result_str += "  - Network Interfaces: Updated\n"
                if disks:
                    result_str += "  - Disks: Updated\n"
                if labels:
                    result_str += "  - Labels: Updated\n"
                if metadata:
                    result_str += "  - Metadata: Updated\n"
                result_str += f"Operation: {result.name}, Status: {result.status}"
                
                return result_str
            except Exception as e:
                logger.error(f"Error modifying instance: {e}")
                return f"Failed to modify instance '{name}' in zone {zone}: {str(e)}"
        
        @self.mcp.tool()
        async def restart_instance(name: str, zone: str) -> str:
            """
            Restart a GCP instance (stop and then start).
            
            Args:
                name: Name of the instance to restart
                zone: Zone where the instance is located
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # First stop the instance
                stop_result = self.gcp_service.stop_instance(zone, name)
                
                # Wait for the instance to stop (in production, would use GCP operation polling)
                # For simplicity, we're just waiting a fixed amount of time
                await asyncio.sleep(10)
                
                # Then start the instance
                start_result = self.gcp_service.start_instance(zone, name)
                
                return f"Restarting instance '{name}' in zone {zone}. Stop operation: {stop_result.name}, Start operation: {start_result.name}"
            except Exception as e:
                logger.error(f"Error restarting instance: {e}")
                return f"Failed to restart instance '{name}' in zone {zone}: {str(e)}"
        
        @self.mcp.tool()
        async def add_disk(
            name: str,
            zone: str,
            disk_name: str,
            size_gb: int = 10,
            disk_type: str = "pd-standard",
            auto_delete: bool = True,
            mode: str = "READ_WRITE"
        ) -> str:
            """
            Add a new disk to an existing instance.
            
            Args:
                name: Name of the instance
                zone: Zone where the instance is located
                disk_name: Name for the new disk
                size_gb: Size of the disk in GB (default: 10)
                disk_type: Type of disk (default: pd-standard)
                auto_delete: Whether to auto-delete when instance is deleted (default: True)
                mode: Mode of attachment (READ_WRITE or READ_ONLY, default: READ_WRITE)
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Prepare disk configuration
                disk_config = {
                    'name': disk_name,
                    'size_gb': size_gb,
                    'disk_type': disk_type,
                    'auto_delete': auto_delete,
                    'mode': mode
                }
                
                # Add the disk
                result = self.gcp_service.add_disk(zone, name, disk_config)
                
                return f"Adding disk '{disk_name}' to instance '{name}' in zone {zone}.\n" \
                       f"Size: {size_gb}GB, Type: {disk_type}, Mode: {mode}\n" \
                       f"Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error adding disk: {e}")
                return f"Failed to add disk to instance '{name}' in zone {zone}: {str(e)}"
        
        @self.mcp.tool()
        async def modify_disk(
            name: str,
            zone: str,
            disk_name: str,
            size_gb: Optional[int] = None,
            disk_type: Optional[str] = None
        ) -> str:
            """
            Modify an existing disk attached to an instance.
            
            Args:
                name: Name of the instance
                zone: Zone where the instance is located
                disk_name: Name of the disk to modify
                size_gb: New size in GB
                disk_type: New disk type (e.g., pd-standard, pd-ssd)
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Modify the disk
                result = self.gcp_service.modify_disk(
                    zone=zone,
                    name=name,
                    disk_name=disk_name,
                    size_gb=size_gb,
                    disk_type=disk_type
                )
                
                # Format response
                result_str = f"Modifying disk '{disk_name}' on instance '{name}' in zone {zone}.\n"
                if size_gb:
                    result_str += f"  - New size: {size_gb}GB\n"
                if disk_type:
                    result_str += f"  - New type: {disk_type}\n"
                result_str += f"Operation: {result.name}, Status: {result.status}"
                
                return result_str
            except Exception as e:
                logger.error(f"Error modifying disk: {e}")
                return f"Failed to modify disk on instance '{name}' in zone {zone}: {str(e)}"
        
        @self.mcp.tool()
        async def attach_disk(
            name: str,
            zone: str,
            disk_name: str,
            auto_delete: bool = True,
            mode: str = "READ_WRITE"
        ) -> str:
            """
            Attach an existing disk to an instance.
            
            Args:
                name: Name of the instance
                zone: Zone where the instance is located
                disk_name: Name of the disk to attach
                auto_delete: Whether to auto-delete when instance is deleted (default: True)
                mode: Mode of attachment (READ_WRITE or READ_ONLY, default: READ_WRITE)
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Attach the disk
                result = self.gcp_service.attach_disk(
                    zone=zone,
                    name=name,
                    disk_name=disk_name,
                    auto_delete=auto_delete,
                    mode=mode
                )
                
                return f"Attaching disk '{disk_name}' to instance '{name}' in zone {zone}.\n" \
                       f"Mode: {mode}, Auto-delete: {auto_delete}\n" \
                       f"Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error attaching disk: {e}")
                return f"Failed to attach disk to instance '{name}' in zone {zone}: {str(e)}"
        
        @self.mcp.tool()
        async def detach_disk(
            name: str,
            zone: str,
            device_name: str
        ) -> str:
            """
            Detach a disk from an instance.
            
            Args:
                name: Name of the instance
                zone: Zone where the instance is located
                device_name: Device name of the disk to detach
            """
            try:
                # Check if instance exists
                existing = self.gcp_service.get_instance(zone, name)
                if not existing:
                    return f"Instance '{name}' not found in zone {zone}."
                
                # Detach the disk
                result = self.gcp_service.detach_disk(
                    zone=zone,
                    name=name,
                    device_name=device_name
                )
                
                return f"Detaching disk '{device_name}' from instance '{name}' in zone {zone}.\n" \
                       f"Operation: {result.name}, Status: {result.status}"
            except Exception as e:
                logger.error(f"Error detaching disk: {e}")
                return f"Failed to detach disk from instance '{name}' in zone {zone}: {str(e)}"