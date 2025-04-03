import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional, Union, Any

import httpx
from fastapi import FastAPI
from google.oauth2 import service_account
from googleapiclient import discovery
from mcp.server.fastmcp import FastMCP
from mcp.types import Request, Result
from pydantic import BaseModel, Field
from src.core.instance import GCPService
from src.handler.intent_parser import IntentParser
from src.models.models import GCPInstance, GCPInstanceList, GCPOperationResult
from src.server.config import GCP_CREDENTIALS_PATH, GCP_PROJECT_ID, GCP_ZONE, MCP_HOST, MCP_PORT, logger
class MCPHandler:
    """
    Handler for MCP requests.
    Processes intents and delegates to GCP service for execution.
    """
    mcp=FastMCP("gcp-instance-manager")
    def __init__(self, gcp_service: GCPService):
        """Initialize with a GCP service."""
        self.gcp_service = gcp_service
    
    async def handle_request(self, request: Request) -> Result:
        """
        Handle an MCP request by parsing intent and executing the corresponding action.
        
        Args:
            request: The MCP request containing prompt text
            
        Returns:
            Response: The MCP response with execution results
        """
        try:
            # Parse the intent from the prompt text
            prompt = request.prompt.strip()
            intent_data = IntentParser.parse(prompt)
            
            if not intent_data:
                return Result(
                    content="I couldn't understand your intent. Please try again with a clearer command."
                )
            
            intent = intent_data["intent"]
            
            # Handle different intents
            if intent == "list":
                return await self._handle_list(intent_data)
            elif intent == "get":
                return await self._handle_get(intent_data)
            elif intent == "create":
                return await self._handle_create(intent_data)
            elif intent == "delete":
                return await self._handle_delete(intent_data)
            elif intent == "modify":
                return await self._handle_modify(intent_data)
            elif intent == "start":
                return await self._handle_start(intent_data)
            elif intent == "stop":
                return await self._handle_stop(intent_data)
            elif intent == "restart":
                return await self._handle_restart(intent_data)
            else:
                return Result(
                    content=f"Unsupported intent: {intent}"
                )
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return Result(
                content=f"An error occurred: {str(e)}"
            )
    @mcp.tool()
    async def _handle_list(self, intent_data: Dict[str, str]) -> Result:
        """Handle list instances intent."""
        zone = intent_data.get("zone", GCP_ZONE)
        
        try:
            instance_list = self.gcp_service.list_instances(zone)
            
            if not instance_list.instances:
                return Result(
                    content=f"No instances found in zone {zone}."
                )
            
            # Format the response
            content = f"Instances in zone {zone}:\n\n"
            for instance in instance_list.instances:
                content += f"- {instance.name} ({instance.machine_type}): {instance.status}\n"
            
            return Result(
                content=content
            )
        except Exception as e:
            logger.error(f"Error listing instances: {e}")
            return Result(
                content=f"Failed to list instances in zone {zone}: {str(e)}"
            )
    @mcp.tool()
    async def _handle_get(self, intent_data: Dict[str, str]) -> Result:
        """Handle get instance intent."""
        name = intent_data.get("name")
        zone = intent_data.get("zone", GCP_ZONE)
        
        try:
            instance = self.gcp_service.get_instance(zone, name)
            
            if not instance:
                return Result(
                    content=f"Instance '{name}' not found in zone {zone}."
                )
            
            # Format the response
            content = f"Instance Details: {instance.name}\n"
            content += f"  Zone: {zone}\n"
            content += f"  Machine Type: {instance.machine_type}\n"
            content += f"  Status: {instance.status}\n"
            
            # Add network information
            if instance.network_interfaces:
                content += "  Network Interfaces:\n"
                for ni in instance.network_interfaces:
                    content += f"    - Network: {ni.get('network', '').split('/')[-1]}\n"
                    content += f"      IP: {ni.get('networkIP', '')}\n"
                    
                    # Add access configs (external IPs)
                    for ac in ni.get('accessConfigs', []):
                        if 'natIP' in ac:
                            content += f"      External IP: {ac.get('natIP', '')}\n"
            
            # Add disk information
            if instance.disks:
                content += "  Disks:\n"
                for disk in instance.disks:
                    disk_name = disk.get('source', '').split('/')[-1]
                    content += f"    - {disk_name} (Boot: {disk.get('boot', False)})\n"
            
            # Add labels if present
            if instance.labels:
                content += "  Labels:\n"
                for k, v in instance.labels.items():
                    content += f"    - {k}: {v}\n"
            
            # Add metadata if present
            if instance.metadata and 'items' in instance.metadata:
                content += "  Metadata:\n"
                for item in instance.metadata.get('items', []):
                    content += f"    - {item.get('key')}: {item.get('value')}\n"
            
            return Result(
                content=content
            )
        except Exception as e:
            logger.error(f"Error getting instance details: {e}")
            return Result(
                content=f"Failed to get details for instance '{name}' in zone {zone}: {str(e)}"
            )
    @mcp.tool()
    async def _handle_create(self, intent_data: Dict[str, Any]) -> Result:
        """Handle create instance intent."""
        name = intent_data.get("name")
        zone = intent_data.get("zone", GCP_ZONE)
        machine_type = intent_data.get("machine_type", "n1-standard-1")
        labels = intent_data.get("labels", {})
        metadata = intent_data.get("metadata", {})
        
        try:
            # Create instance object
            instance = GCPInstance(
                name=name,
                machine_type=machine_type,
                zone=zone,
                labels=labels,
                metadata=metadata
            )
            
            # Check if instance already exists
            existing = self.gcp_service.get_instance(zone, name)
            if existing:
                return Result(
                    content=f"Instance '{name}' already exists in zone {zone}."
                )
            
            # Create the instance
            result = self.gcp_service.create_instance(instance)
            
            return Result(
                content=f"Creating instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            )
        except Exception as e:
            logger.error(f"Error creating instance: {e}")
            return Result(
                content=f"Failed to create instance '{name}' in zone {zone}: {str(e)}"
            )
    @mcp.tool()
    async def _handle_delete(self, intent_data: Dict[str, str]) -> Result:
        """Handle delete instance intent."""
        name = intent_data.get("name")
        zone = intent_data.get("zone", GCP_ZONE)
        
        try:
            # Check if instance exists
            existing = self.gcp_service.get_instance(zone, name)
            if not existing:
                return Result(
                    content=f"Instance '{name}' not found in zone {zone}."
                )
            
            # Delete the instance
            result = self.gcp_service.delete_instance(zone, name)
            
            return Result(
                content=f"Deleting instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            )
        except Exception as e:
            logger.error(f"Error deleting instance: {e}")
            return Result(
                content=f"Failed to delete instance '{name}' in zone {zone}: {str(e)}"
            )
    @mcp.tool()
    async def _handle_modify(self, intent_data: Dict[str, Any]) -> Result:
        """Handle modify instance intent."""
        name = intent_data.get("name")
        zone = intent_data.get("zone", GCP_ZONE)
        labels = intent_data.get("labels", {})
        metadata = intent_data.get("metadata", {})
        
        if not labels and not metadata:
            return Result(
                content="No modifications specified. Please provide labels or metadata to update."
            )
        
        try:
            # Check if instance exists
            existing = self.gcp_service.get_instance(zone, name)
            if not existing:
                return Result(
                    content=f"Instance '{name}' not found in zone {zone}."
                )
            
            # Only provide non-empty dictionaries to modify_instance
            labels_arg = labels if labels else None
            metadata_arg = metadata if metadata else None
            
            # Modify the instance
            result = self.gcp_service.modify_instance(zone, name, labels_arg, metadata_arg)
            
            # Prepare response message
            content = f"Modifying instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}\n"
            
            if labels:
                content += "Updated labels:\n"
                for k, v in labels.items():
                    content += f"  - {k}: {v}\n"
            
            if metadata:
                content += "Updated metadata:\n"
                for k, v in metadata.items():
                    content += f"  - {k}: {v}\n"
            
            return Result(
                content=content
            )
        except Exception as e:
            logger.error(f"Error modifying instance: {e}")
            return Result(
                content=f"Failed to modify instance '{name}' in zone {zone}: {str(e)}"
            )
    @mcp.tool()
    async def _handle_start(self, intent_data: Dict[str, str]) -> Result:
        """Handle start instance intent."""
        name = intent_data.get("name")
        zone = intent_data.get("zone", GCP_ZONE)
        
        try:
            # Check if instance exists
            existing = self.gcp_service.get_instance(zone, name)
            if not existing:
                return Result(
                    content=f"Instance '{name}' not found in zone {zone}."
                )
            
            # Check if instance is already running
            if existing.status == "RUNNING":
                return Result(
                    content=f"Instance '{name}' is already running."
                )
            
            # Start the instance
            result = self.gcp_service.start_instance(zone, name)
            
            return Result(
                content=f"Starting instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            )
        except Exception as e:
            logger.error(f"Error starting instance: {e}")
            return Result(
                content=f"Failed to start instance '{name}' in zone {zone}: {str(e)}"
            )
    @mcp.tool()
    async def _handle_stop(self, intent_data: Dict[str, str]) -> Result:
        """Handle stop instance intent."""
        name = intent_data.get("name")
        zone = intent_data.get("zone", GCP_ZONE)
        
        try:
            # Check if instance exists
            existing = self.gcp_service.get_instance(zone, name)
            if not existing:
                return Result(
                    content=f"Instance '{name}' not found in zone {zone}."
                )
            
            # Check if instance is already stopped
            if existing.status == "TERMINATED":
                return Result(
                    content=f"Instance '{name}' is already stopped."
                )
            
            # Stop the instance
            result = self.gcp_service.stop_instance(zone, name)
            
            return Result(
                content=f"Stopping instance '{name}' in zone {zone}. Operation: {result.name}, Status: {result.status}"
            )
        except Exception as e:
            logger.error(f"Error stopping instance: {e}")
            return Result(
                content=f"Failed to stop instance '{name}' in zone {zone}: {str(e)}"
            )
    @mcp.tool()
    async def _handle_restart(self, intent_data: Dict[str, str]) -> Result:
        """Handle restart instance intent."""
        name = intent_data.get("name")
        zone = intent_data.get("zone", GCP_ZONE)
        
        try:
            # Check if instance exists
            existing = self.gcp_service.get_instance(zone, name)
            if not existing:
                return Result(
                    content=f"Instance '{name}' not found in zone {zone}."
                )
            
            # First stop the instance
            stop_result = self.gcp_service.stop_instance(zone, name)
            
            # Wait for the instance to stop (in production, would use GCP operation polling)
            # For simplicity, we're just waiting a fixed amount of time
            await asyncio.sleep(10)
            
            # Then start the instance
            start_result = self.gcp_service.start_instance(zone, name)
            
            return Result(
                content=f"Restarting instance '{name}' in zone {zone}. Stop operation: {stop_result.name}, Start operation: {start_result.name}"
            )
        except Exception as e:
            logger.error(f"Error restarting instance: {e}")
            return Result(
                content=f"Failed to restart instance '{name}' in zone {zone}: {str(e)}"
            )