from mcp.server.fastmcp import FastMCP
import subprocess
import logging
import logging.handlers
import os
import sys
from typing import List, Dict, Optional
from dotenv import load_dotenv
from logger_config import setup_logging, get_logger, log_performance

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(
    log_level=logging.DEBUG,
    log_file_path='logs/moderne_mcp.log'
)
logger = get_logger(__name__)

# Constants
MODERNE_CLI_JAR = os.getenv('MODERNE_CLI_JAR', "C:\\Users\\rajap\\tools\\moderne-cli-3.36.1.jar")
PROJECTS_BASE_PATH = os.getenv('PROJECTS_BASE_PATH')
logger.info("Moderne server initialization", 
           extra={"moderne_cli_jar": MODERNE_CLI_JAR, "projects_base_path": PROJECTS_BASE_PATH})

# Initialize MCP server
logger.info("Initializing Moderne MCP server")
mcp = FastMCP("ModerneMCP")

@log_performance(logger)
def get_full_project_path(project_name: str) -> str:
    """Get the full project path from the project name."""
    if not PROJECTS_BASE_PATH:
        logger.error("PROJECTS_BASE_PATH environment variable not set")
        raise ValueError("PROJECTS_BASE_PATH environment variable not set")
    full_path = os.path.join(PROJECTS_BASE_PATH, project_name)
    logger.debug("Project path resolved", extra={"project_name": project_name, "full_path": full_path})
    return full_path

@log_performance(logger)
def verify_jar_exists():
    """Verify that the Moderne CLI JAR file exists."""
    if not os.path.exists(MODERNE_CLI_JAR):
        logger.error("Moderne CLI JAR not found", extra={"jar_path": MODERNE_CLI_JAR})
        raise FileNotFoundError(f"Moderne CLI JAR not found: {MODERNE_CLI_JAR}")
    logger.debug("Moderne CLI JAR verified", extra={"jar_path": MODERNE_CLI_JAR})

@log_performance(logger)
def run_moderne_command(command: list) -> dict:
    """Run a Moderne CLI command and return the result."""
    logger.info("Executing Moderne CLI command", extra={"command": ' '.join(command)})
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Command executed successfully", 
                       extra={"returncode": result.returncode})
            logger.debug("Command output", extra={"stdout": result.stdout})
        else:
            logger.error("Command execution failed", 
                        extra={
                            "returncode": result.returncode,
                            "stderr": result.stderr
                        })
            
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr
        }
    except Exception as e:
        logger.error("Command execution error", 
                    extra={"error": str(e), "command": ' '.join(command)},
                    exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

@log_performance(logger)
def get_all_projects() -> List[str]:
    """Get list of all projects in PROJECTS_BASE_PATH."""
    if not PROJECTS_BASE_PATH:
        logger.error("PROJECTS_BASE_PATH environment variable not set")
        raise ValueError("PROJECTS_BASE_PATH environment variable not set")
        
    try:
        projects = [d for d in os.listdir(PROJECTS_BASE_PATH) 
                   if os.path.isdir(os.path.join(PROJECTS_BASE_PATH, d))]
        logger.info("Projects found", 
                   extra={"count": len(projects), "projects": projects})
        return projects
    except Exception as e:
        logger.error("Error reading projects directory", 
                    extra={"path": PROJECTS_BASE_PATH, "error": str(e)},
                    exc_info=True)
        raise

@log_performance(logger)
def verify_project_exists(project_name: str) -> bool:
    """Verify that a project exists in PROJECTS_BASE_PATH."""
    try:
        project_path = get_full_project_path(project_name)
        exists = os.path.exists(project_path)
        if exists:
            logger.debug("Project verified", 
                        extra={"project_name": project_name, "path": project_path})
        else:
            logger.warning("Project not found", 
                         extra={"project_name": project_name, "path": project_path})
        return exists
    except Exception as e:
        logger.error("Project verification error", 
                    extra={"project_name": project_name, "error": str(e)},
                    exc_info=True)
        return False

@mcp.tool(name="modBuildAll", description="Build all projects using Moderne CLI")
@log_performance(logger)
def mod_build_all() -> dict:
    """Build all projects in PROJECTS_BASE_PATH using Moderne CLI."""
    logger.info("Starting modBuildAll")
    
    try:
        projects = get_all_projects()
        if not projects:
            logger.warning("No projects found to build")
            return {"success": False, "error": "No projects found"}
            
        results = []
        success_count = 0
        
        for project in projects:
            logger.info("Building project", extra={"project": project})
            result = mod_build(project)
            results.append({
                "project": project,
                "success": result["success"],
                "error": result.get("error", None)
            })
            if result["success"]:
                success_count += 1
                
        logger.info("Build all completed", 
                   extra={
                       "total_projects": len(projects),
                       "successful_builds": success_count,
                       "results": results
                   })
                
        return {
            "success": success_count > 0,
            "total_projects": len(projects),
            "successful_builds": success_count,
            "results": results
        }
        
    except Exception as e:
        logger.error("Error in modBuildAll", 
                    extra={"error": str(e)},
                    exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool(name="modUpgradeAll", description="Upgrade all projects using specified recipe")
@log_performance(logger)
def mod_upgrade_all(params: str) -> dict:
    """Upgrade all projects using specified recipe."""
    logger.info("Starting modUpgradeAll", extra={"recipe": params})
    
    try:
        projects = get_all_projects()
        if not projects:
            logger.warning("No projects found to upgrade")
            return {"success": False, "error": "No projects found"}
            
        results = []
        success_count = 0
        
        for project in projects:
            logger.info("Upgrading project", 
                       extra={"project": project, "recipe": params})
            result = mod_upgrade(project, params)
            results.append({
                "project": project,
                "success": result["success"],
                "error": result.get("error", None)
            })
            if result["success"]:
                success_count += 1
                
        logger.info("Upgrade all completed", 
                   extra={
                       "total_projects": len(projects),
                       "successful_upgrades": success_count,
                       "results": results
                   })
                
        return {
            "success": success_count > 0,
            "total_projects": len(projects),
            "successful_upgrades": success_count,
            "results": results
        }
        
    except Exception as e:
        logger.error("Error in modUpgradeAll", 
                    extra={"error": str(e), "recipe": params},
                    exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool(name="modApplyUpgradeAll", description="Apply the last recipe run to all projects")
def mod_apply_upgrade_all() -> dict:
    """Apply the last recipe run to all projects using Moderne CLI."""
    logger.info("Starting modApplyUpgradeAll")
    
    try:
        projects = get_all_projects()
        if not projects:
            logger.warning("No projects found to apply upgrades")
            return {"success": False, "error": "No projects found"}
            
        results = []
        success_count = 0
        
        for project in projects:
            logger.info(f"Applying upgrade to project: {project}")
            result = mod_apply_upgrade(project)
            results.append({
                "project": project,
                "success": result["success"],
                "error": result.get("error", None)
            })
            if result["success"]:
                success_count += 1
                
        return {
            "success": success_count > 0,
            "total_projects": len(projects),
            "successful_applies": success_count,
            "results": results
        }
        
    except Exception as e:
        logger.error("Error in modApplyUpgradeAll", exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool(name="modBuild", description="Build a project using Moderne CLI")
def mod_build(project_name: str) -> dict:
    """Build a project using Moderne CLI."""
    logger.info(f"Starting modBuild for project: {project_name}")
    
    try:
        verify_jar_exists()
        
        if not verify_project_exists(project_name):
            return {"success": False, "error": f"Project not found: {project_name}"}
            
        project_path = get_full_project_path(project_name)
        command = ["java", "-jar", MODERNE_CLI_JAR, "build", project_path]
        return run_moderne_command(command)
        
    except Exception as e:
        logger.error("Error in modBuild", exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool(name="modUpgrade", description="Upgrade a project using specified recipe")
def mod_upgrade(project_name: str, recipe: str) -> dict:
    """Upgrade a project using specified recipe."""
    try:
        logger.info(f"Starting modUpgrade for project: {project_name}")
        logger.info(f"Using recipe: {recipe}")
        
        verify_jar_exists()
        
        if not verify_project_exists(project_name):
            return {"success": False, "error": f"Project not found: {project_name}"}
            
        project_path = get_full_project_path(project_name)
        command = ["java", "-jar", MODERNE_CLI_JAR, "run", project_path, "--recipe", recipe]
        return run_moderne_command(command)
        
    except Exception as e:
        logger.error("Error in modUpgrade", exc_info=True)
        return {"success": False, "error": str(e)}

@mcp.tool(name="modApplyUpgrade", description="Apply the last recipe run using Moderne CLI")
def mod_apply_upgrade(project_name: str) -> dict:
    """Apply the last recipe run using Moderne CLI."""
    logger.info(f"Starting modApplyUpgrade for project: {project_name}")
    
    try:
        verify_jar_exists()
        
        if not verify_project_exists(project_name):
            return {"success": False, "error": f"Project not found: {project_name}"}
            
        project_path = get_full_project_path(project_name)
        command = ["java", "-jar", MODERNE_CLI_JAR, "git", "apply", project_path, "--last-recipe-run"]
        return run_moderne_command(command)
        
    except Exception as e:
        logger.error("Error in modApplyUpgrade", exc_info=True)
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    try:
        # Verify environment
        if not PROJECTS_BASE_PATH:
            logger.error("PROJECTS_BASE_PATH environment variable not set")
            sys.exit(1)
            
        if not os.path.exists(MODERNE_CLI_JAR):
            logger.error(f"Moderne CLI JAR not found at: {MODERNE_CLI_JAR}")
            sys.exit(1)
            
        # Start the MCP server with stdio transport
        logger.info("Starting Moderne MCP server with stdio transport")
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        mcp.run(transport="stdio")
        
    except Exception as e:
        logger.error(f"Error starting Moderne MCP server: {e}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0) 