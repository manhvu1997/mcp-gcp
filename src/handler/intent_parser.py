import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field
from src.server.config import GCP_ZONE, logger

class IntentParser:
    """
    Parse natural language intents related to GCP instance management.
    Uses pattern matching to identify operations and extract parameters.
    """
    
    @staticmethod
    def parse_list_intent(text: str) -> Optional[Dict[str, str]]:
        """
        Parse intent to list instances.
        
        Example intents:
        - "List all instances"
        - "Show instances in us-central1-a"
        - "Get all GCP VMs"
        """
        patterns = [
            r"(?i)list\s+(?:all\s+)?instances(?:\s+in\s+([a-z0-9\-]+))?",
            r"(?i)show\s+(?:all\s+)?(?:instances|vms)(?:\s+in\s+([a-z0-9\-]+))?",
            r"(?i)get\s+(?:all\s+)?(?:instances|vms)(?:\s+in\s+([a-z0-9\-]+))?"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                zone = match.group(1) if match.groups() and match.group(1) else GCP_ZONE
                return {"intent": "list", "zone": zone}
        
        return None
    
    @staticmethod
    def parse_get_intent(text: str) -> Optional[Dict[str, str]]:
        """
        Parse intent to get a specific instance.
        
        Example intents:
        - "Get instance my-instance"
        - "Show details for instance web-server in us-central1-a"
        - "Describe VM database-1"
        """
        patterns = [
            r"(?i)get\s+instance\s+([a-zA-Z0-9\-]+)(?:\s+in\s+([a-z0-9\-]+))?",
            r"(?i)show\s+details\s+for\s+(?:instance|vm)\s+([a-zA-Z0-9\-]+)(?:\s+in\s+([a-z0-9\-]+))?",
            r"(?i)describe\s+(?:instance|vm)\s+([a-zA-Z0-9\-]+)(?:\s+in\s+([a-z0-9\-]+))?"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1)
                zone = match.group(2) if match.groups() and len(match.groups()) > 1 and match.group(2) else GCP_ZONE
                return {"intent": "get", "name": name, "zone": zone}
        
        return None
    
    @staticmethod
    def parse_create_intent(text: str) -> Optional[Dict[str, Any]]:
        """
        Parse intent to create a new instance.
        
        Example intents:
        - "Create instance my-instance"
        - "Create a new VM web-server with machine type n1-standard-2 in us-central1-a"
        - "Launch instance database-1 with label env=prod"
        """
        # Basic pattern to match create intents
        create_pattern = r"(?i)(?:create|launch)\s+(?:a\s+new\s+)?(?:instance|vm)\s+([a-zA-Z0-9\-]+)"
        match = re.search(create_pattern, text)
        
        if not match:
            return None
            
        name = match.group(1)
        result = {"intent": "create", "name": name, "zone": GCP_ZONE, "machine_type": "n1-standard-1", "labels": {}, "metadata": {}}
        
        # Extract machine type if specified
        machine_pattern = r"(?i)(?:with\s+)?machine\s+type\s+([a-zA-Z0-9\-]+)"
        machine_match = re.search(machine_pattern, text)
        if machine_match:
            result["machine_type"] = machine_match.group(1)
        
        # Extract zone if specified
        zone_pattern = r"(?i)in\s+zone\s+([a-z0-9\-]+)"
        zone_match = re.search(zone_pattern, text)
        if zone_match:
            result["zone"] = zone_match.group(1)
        
        # Extract labels if specified
        label_pattern = r"(?i)with\s+label\s+([a-zA-Z0-9\-]+)=([a-zA-Z0-9\-]+)"
        for label_match in re.finditer(label_pattern, text):
            key, value = label_match.groups()
            result["labels"][key] = value
        
        return result
    
    @staticmethod
    def parse_delete_intent(text: str) -> Optional[Dict[str, str]]:
        """
        Parse intent to delete an instance.
        
        Example intents:
        - "Delete instance my-instance"
        - "Remove VM web-server in us-central1-a"
        - "Terminate instance database-1"
        """
        patterns = [
            r"(?i)delete\s+instance\s+([a-zA-Z0-9\-]+)(?:\s+in\s+([a-z0-9\-]+))?",
            r"(?i)remove\s+(?:instance|vm)\s+([a-zA-Z0-9\-]+)(?:\s+in\s+([a-z0-9\-]+))?",
            r"(?i)terminate\s+instance\s+([a-zA-Z0-9\-]+)(?:\s+in\s+([a-z0-9\-]+))?"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1)
                zone = match.group(2) if match.groups() and len(match.groups()) > 1 and match.group(2) else GCP_ZONE
                return {"intent": "delete", "name": name, "zone": zone}
        
        return None
    
    @staticmethod
    def parse_modify_intent(text: str) -> Optional[Dict[str, Any]]:
        """
        Parse intent to modify an instance.
        
        Example intents:
        - "Update instance my-instance with label env=prod"
        - "Set metadata user=john on VM web-server"
        - "Change labels for instance database-1 to env=dev,project=demo"
        """
        # Basic pattern to match modify intents
        modify_pattern = r"(?i)(?:update|modify|change)\s+(?:instance|vm)\s+([a-zA-Z0-9\-]+)"
        match = re.search(modify_pattern, text)
        
        # Alternative pattern for setting metadata
        metadata_pattern = r"(?i)set\s+metadata\s+([a-zA-Z0-9\-]+)=([a-zA-Z0-9\-]+)\s+on\s+(?:instance|vm)\s+([a-zA-Z0-9\-]+)"
        metadata_match = re.search(metadata_pattern, text)
        
        # Alternative pattern for setting labels
        labels_pattern = r"(?i)set\s+labels?\s+for\s+(?:instance|vm)\s+([a-zA-Z0-9\-]+)\s+to\s+([a-zA-Z0-9\-,=]+)"
        labels_match = re.search(labels_pattern, text)
        
        result = {"intent": "modify", "labels": {}, "metadata": {}, "zone": GCP_ZONE}
        
        if match:
            result["name"] = match.group(1)
            
            # Extract labels if specified
            label_pattern = r"(?i)with\s+labels?\s+([a-zA-Z0-9\-]+)=([a-zA-Z0-9\-]+)"
            for label_match in re.finditer(label_pattern, text):
                key, value = label_match.groups()
                result["labels"][key] = value
            
            # Extract metadata if specified
            metadata_pattern = r"(?i)with\s+metadata\s+([a-zA-Z0-9\-]+)=([a-zA-Z0-9\-]+)"
            for metadata_match in re.finditer(metadata_pattern, text):
                key, value = metadata_match.groups()
                result["metadata"][key] = value
            
            # Extract zone if specified
            zone_pattern = r"(?i)in\s+zone\s+([a-z0-9\-]+)"
            zone_match = re.search(zone_pattern, text)
            if zone_match:
                result["zone"] = zone_match.group(1)
                
            return result
        
        elif metadata_match:
            key, value, name = metadata_match.groups()
            result["name"] = name
            result["metadata"][key] = value
            
            # Extract zone if specified
            zone_pattern = r"(?i)in\s+zone\s+([a-z0-9\-]+)"
            zone_match = re.search(zone_pattern, text)
            if zone_match:
                result["zone"] = zone_match.group(1)
                
            return result
        
        elif labels_match:
            name, labels_str = labels_match.groups()
            result["name"] = name
            
            # Parse comma-separated labels
            for label_pair in labels_str.split(','):
                if '=' in label_pair:
                    key, value = label_pair.split('=')
                    result["labels"][key.strip()] = value.strip()
            
            # Extract zone if specified
            zone_pattern = r"(?i)in\s+zone\s+([a-z0-9\-]+)"
            zone_match = re.search(zone_pattern, text)
            if zone_match:
                result["zone"] = zone_match.group(1)
                
            return result
        
        return None
    
    @staticmethod
    def parse_start_stop_intent(text: str) -> Optional[Dict[str, str]]:
        """
        Parse intent to start or stop an instance.
        
        Example intents:
        - "Start instance my-instance"
        - "Stop VM web-server in us-central1-a"
        - "Restart instance database-1"
        """
        patterns = [
            r"(?i)(start|stop|restart)\s+(?:instance|vm)\s+([a-zA-Z0-9\-]+)(?:\s+in\s+([a-z0-9\-]+))?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                action, name = match.group(1), match.group(2)
                zone = match.group(3) if match.groups() and len(match.groups()) > 2 and match.group(3) else GCP_ZONE
                
                if action.lower() == "restart":
                    # For restart, we'll use "stop" intent and handle the restart in the controller
                    return {"intent": "restart", "name": name, "zone": zone}
                else:
                    return {"intent": action.lower(), "name": name, "zone": zone}
        
        return None
    
    @staticmethod
    def parse(text: str) -> Optional[Dict[str, Any]]:
        """
        Parse the intent from the given text.
        Tries different intent parsers and returns the first match.
        """
        parsers = [
            IntentParser.parse_list_intent,
            IntentParser.parse_get_intent,
            IntentParser.parse_create_intent,
            IntentParser.parse_delete_intent,
            IntentParser.parse_modify_intent,
            IntentParser.parse_start_stop_intent
        ]
        
        for parser in parsers:
            result = parser(text)
            if result:
                return result
        
        return None