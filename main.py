import argparse
import logging
from src.server.config import MCP_HOST, MCP_PORT, GCP_PROJECT_ID, GCP_CREDENTIALS_PATH, LOG_LEVEL
from src.server.mcpserver import MCPServer

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='MCP Server for GCP Instance Management')
    parser.add_argument('--host', type=str, default=MCP_HOST, help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=MCP_PORT, help='Port to listen on')
    parser.add_argument('--project', type=str, default=GCP_PROJECT_ID, help='GCP Project ID')
    parser.add_argument('--credentials', type=str, default=GCP_CREDENTIALS_PATH, help='Path to GCP credentials JSON file')
    parser.add_argument('--transport', type=str, default='stdio', choices=['stdio', 'sse'], 
                        help='Transport mechanism to use (stdio or sse)')
    
    args = parser.parse_args()
    
    # Override environment variables if provided via CLI
    project_id = args.project if args.project else GCP_PROJECT_ID
    credentials_path = args.credentials if args.credentials else GCP_CREDENTIALS_PATH
    
    # Check if required config is available
    if not project_id:
        logger.error("GCP Project ID is required. Set it with GCP_PROJECT_ID environment variable or --project flag.")
        return
        
    logger.info(f"Starting MCP server with project: {project_id}")
    
    # Create server
    server = MCPServer(project_id=project_id, credentials_path=credentials_path)
    
    transport_args = {}
    if args.transport == 'sse':
        transport_args = {
            'host': args.host, 
            'port': args.port
        }
    
    # Run the server with the specified transport
    server.run(transport=args.transport, transport_args=transport_args)

if __name__ == "__main__":
    main()