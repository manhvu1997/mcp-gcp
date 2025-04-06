"""
MCP Server implementation for GCP instance management.
Based on the official MCP documentation.
"""
import logging
from mcp.server.fastmcp import FastMCP

# Import from local modules
from src.server.config import MCP_HOST, MCP_PORT, GCP_PROJECT_ID, GCP_CREDENTIALS_PATH  
from src.core.instance import GCPService
from src.handler.tools import GCPTools
from src.handler.gke_tools import GKETools
from src.core.gke_service import GKEService
logger = logging.getLogger(__name__)

class MCPServer:
    """
    Main MCP server implementation.
    Sets up FastMCP and registers tools for GCP instance management.
    """
    
    def __init__(self, project_id=None, credentials_path=None):
        """
        Initialize the MCP server.
        
        Args:
            project_id: GCP project ID (defaults to config value)
            credentials_path: Path to GCP credentials file (defaults to config value)
        """
        # Use provided values or defaults from config
        self.project_id = project_id or GCP_PROJECT_ID
        self.credentials_path = credentials_path or GCP_CREDENTIALS_PATH
        
        # Initialize FastMCP
        self.mcp = FastMCP("gcp-instance-manager")
        
        # Initialize GCP service
        self.gcp_service = GCPService(
            project_id=self.project_id,
            credentials_path=self.credentials_path
        )
        
        # Initialize GKE service
        self.gke_service = GKEService(
            project_id=self.project_id,
            credentials_path=self.credentials_path
        )
        
        # Initialize and register tools
        self.gcp_tools = None
        self.gke_tools = None
    
    def setup(self):
        """Setup the MCP server and components."""
        try:
            # Initialize GCP service
            self.gcp_service.initialize()
            
            # Initialize GKE service
            self.gke_service.initialize()
            
            # Register tools with MCP
            self.gcp_tools = GCPTools(self.gcp_service, self.mcp)
            self.gke_tools = GKETools(self.gke_service, self.mcp)
            
            logger.info(f"MCP server setup complete with tools registered")
        except Exception as e:
            logger.error(f"Error setting up MCP server: {e}")
            raise
    
    def run(self, transport='stdio', transport_args=None):
        """
        Run the MCP server with the specified transport.
        
        Args:
            transport: The transport to use ('sse', 'stdio', etc.)
            transport_args: Additional arguments for the transport
        """
        try:
            # Setup before starting
            self.setup()
            
            # Set default transport_args based on transport type if not provided
            if transport_args is None:
                transport_args = {}
                
                if transport == 'sse':
                    transport_args = {
                        'host': MCP_HOST,
                        'port': MCP_PORT
                    }
            
            # Log transport information
            transport_info = f"{transport}"
            if transport_args:
                transport_info += f" with args: {transport_args}"
            logger.info(f"Starting MCP server with {transport_info}")
            
            # Run the MCP server with the specified transport
            if transport_args:
                self.mcp.run(transport=transport, **transport_args)
            else:
                self.mcp.run(transport=transport)
                
        except Exception as e:
            logger.error(f"Error running MCP server: {e}")
            raise