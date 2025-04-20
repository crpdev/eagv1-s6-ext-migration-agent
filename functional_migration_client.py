import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, Callable, List, AsyncGenerator
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager

from models import (
    MigrationPreferences, MigrationStrategy, TargetVersion,
    ProjectAnalysis, MigrationPlan, AgentState
)
from logger_config import setup_logging

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(
    log_level="INFO",
    log_file=f"logs/java_migration_client_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
logger = logging.getLogger(__name__)

# Type aliases
SessionPair = Tuple[ClientSession, ClientSession]
ToolResult = Dict[str, Any]

@asynccontextmanager
async def create_sessions() -> SessionPair:
    """Create and initialize Moderne and Maven sessions."""
    moderne_session = None
    maven_session = None
    
    try:
        logger.info("Creating MCP sessions")
        
        # Get current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create server parameters with full paths
        moderne_params = StdioServerParameters(
            command=sys.executable,  # Use current Python interpreter
            args=[os.path.join(current_dir, "moderne_mcp_server.py")],
            env=os.environ.copy()  # Pass current environment
        )
        maven_params = StdioServerParameters(
            command=sys.executable,  # Use current Python interpreter
            args=[os.path.join(current_dir, "maven_op.py")],
            env=os.environ.copy()  # Pass current environment
        )
        
        logger.debug("Starting Moderne server subprocess")
        async with stdio_client(moderne_params) as (moderne_read, moderne_write):
            logger.debug("Starting Maven server subprocess")
            async with stdio_client(maven_params) as (maven_read, maven_write):
                logger.debug("Creating Moderne session")
                async with ClientSession(moderne_read, moderne_write) as moderne_session:
                    logger.debug("Creating Maven session")
                    async with ClientSession(maven_read, maven_write) as maven_session:
                        logger.debug("Initializing Moderne session")
                        await moderne_session.initialize()
                        logger.debug("Initializing Maven session")
                        await maven_session.initialize()
                        
                        logger.info("Both sessions initialized successfully")
                        yield moderne_session, maven_session
                
    except Exception as e:
        logger.error(f"Error creating sessions: {str(e)}", exc_info=True)
        raise
    finally:
        logger.debug("Cleaning up sessions")

async def analyze_project(
    sessions: SessionPair,
    preferences: MigrationPreferences
) -> Optional[ProjectAnalysis]:
    """Analyze project structure and dependencies."""
    try:
        logger.info("Starting project analysis", 
                   extra={"project_dir": preferences.project_directory})
        
        moderne_session, maven_session = sessions
        maven_analysis = await maven_session.call_tool("analyzeProject")
        
        if not maven_analysis:
            logger.error("Failed to analyze project with Maven tools")
            return None
            
        analysis_data = maven_analysis.content[0].text
        
        # Extract project details
        project_analysis = ProjectAnalysis(
            java_version=extract_java_version(analysis_data),
            spring_boot_version=extract_spring_boot_version(analysis_data),
            dependencies=extract_dependencies(analysis_data),
            build_tool="maven"
        )
        
        logger.info("Project analysis completed", 
                   extra={"analysis": project_analysis.model_dump()})
        
        return project_analysis
        
    except Exception as e:
        logger.error(f"Error during project analysis: {str(e)}")
        return None

def extract_java_version(analysis_data: str) -> str:
    """Extract Java version from analysis data."""
    return "11"  # Placeholder implementation

def extract_spring_boot_version(analysis_data: str) -> Optional[str]:
    """Extract Spring Boot version from analysis data."""
    return "2.7.0"  # Placeholder implementation

def extract_dependencies(analysis_data: str) -> Dict[str, str]:
    """Extract dependencies from analysis data."""
    return {}  # Placeholder implementation

async def create_migration_plan(
    sessions: SessionPair,
    current_analysis: ProjectAnalysis,
    strategy: MigrationStrategy,
    target_version: TargetVersion
) -> Optional[MigrationPlan]:
    """Create migration plan based on analysis and preferences."""
    try:
        logger.info("Creating migration plan", 
                   extra={
                       "strategy": strategy,
                       "target_version": target_version,
                       "current_analysis": current_analysis.model_dump()
                   })
        
        moderne_session, _ = sessions
        plan_result = await moderne_session.call_tool(
            "migrationPlan",
            {
                "strategy": strategy,
                "targetVersion": target_version,
                "currentAnalysis": current_analysis.model_dump()
            }
        )
        
        if not plan_result:
            logger.error("Failed to create migration plan")
            return None
            
        plan_data = plan_result.content[0].text
        target_state = determine_target_state(current_analysis, strategy, target_version)
        
        migration_plan = MigrationPlan(
            current_state=current_analysis,
            target_state=target_state,
            required_steps=extract_required_steps(plan_data),
            estimated_effort=estimate_effort(plan_data)
        )
        
        logger.info("Migration plan created", 
                   extra={"plan": migration_plan.model_dump()})
        
        return migration_plan
        
    except Exception as e:
        logger.error(f"Error creating migration plan: {str(e)}")
        return None

def determine_target_state(
    current_analysis: ProjectAnalysis,
    strategy: MigrationStrategy,
    target_version: TargetVersion
) -> ProjectAnalysis:
    """Determine target state based on current analysis and goals."""
    return ProjectAnalysis(
        java_version="17",
        spring_boot_version="3.2.0" if strategy == MigrationStrategy.SPRING_BOOT else None,
        dependencies=current_analysis.dependencies,
        build_tool=current_analysis.build_tool
    )

def extract_required_steps(plan_data: str) -> list:
    """Extract required migration steps from plan data."""
    return [
        "Update Java version",
        "Update Spring Boot version",
        "Update dependencies",
        "Refactor code"
    ]

def estimate_effort(plan_data: str) -> str:
    """Estimate migration effort."""
    return "medium"

async def execute_migration_step(
    sessions: SessionPair,
    plan: MigrationPlan,
    step_index: int
) -> bool:
    """Execute a specific migration step."""
    try:
        if step_index >= len(plan.required_steps):
            logger.error("Invalid step index", 
                       extra={"step_index": step_index, 
                             "total_steps": len(plan.required_steps)})
            return False
            
        step = plan.required_steps[step_index]
        logger.info("Executing migration step", 
                   extra={"step": step, "step_index": step_index})
        
        # Map steps to their execution functions
        step_executors = {
            "Update Java version": update_java_version,
            "Update Spring Boot version": update_spring_boot,
            "Update dependencies": update_dependencies,
            "Refactor code": refactor_code
        }
        
        executor = step_executors.get(step)
        if not executor:
            logger.error(f"Unknown step type: {step}")
            return False
            
        success = await executor(sessions)
        
        if success:
            logger.info("Migration step completed successfully", 
                       extra={"step": step})
        else:
            logger.error("Migration step failed", 
                        extra={"step": step})
            
        return success
        
    except Exception as e:
        logger.error(f"Error executing migration step: {str(e)}")
        return False

async def update_java_version(sessions: SessionPair) -> bool:
    """Update Java version using Maven tools."""
    try:
        _, maven_session = sessions
        result = await maven_session.call_tool("mod_build_all")
        return result is not None
    except Exception as e:
        logger.error(f"Error updating Java version: {str(e)}")
        return False

async def update_spring_boot(sessions: SessionPair) -> bool:
    """Update Spring Boot version using Moderne tools."""
    try:
        moderne_session, _ = sessions
        upgrade_result = await moderne_session.call_tool(
            "mod_upgrade_all",
            {"text": "UpgradeSpringBoot_3_2"}
        )
        
        if not upgrade_result:
            return False
            
        apply_result = await moderne_session.call_tool("mod_apply_upgrade_all")
        return apply_result is not None
        
    except Exception as e:
        logger.error(f"Error updating Spring Boot: {str(e)}")
        return False

async def update_dependencies(sessions: SessionPair) -> bool:
    """Update project dependencies."""
    try:
        _, maven_session = sessions
        result = await maven_session.call_tool("mod_build_all")
        return result is not None
    except Exception as e:
        logger.error(f"Error updating dependencies: {str(e)}")
        return False

async def refactor_code(sessions: SessionPair) -> bool:
    """Refactor code using Moderne tools."""
    try:
        moderne_session, _ = sessions
        result = await moderne_session.call_tool("mod_apply_upgrade_all")
        return result is not None
    except Exception as e:
        logger.error(f"Error refactoring code: {str(e)}")
        return False

async def run_migration(
    sessions: SessionPair,
    preferences: MigrationPreferences
) -> bool:
    """Run the complete migration process."""
    try:
        # 1. Analyze project
        analysis = await analyze_project(sessions, preferences)
        if not analysis:
            return False
            
        # 2. Create migration plan
        plan = await create_migration_plan(
            sessions,
            analysis,
            preferences.migration_strategy,
            preferences.target_version
        )
        if not plan:
            return False
            
        # 3. Execute migration steps
        for step_index in range(len(plan.required_steps)):
            success = await execute_migration_step(sessions, plan, step_index)
            if not success:
                return False
                
        logger.info("Migration completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        return False

async def main():
    """Main entry point."""
    try:
        async with create_sessions() as sessions:
            preferences = MigrationPreferences(
                project_directory=os.getenv("PROJECT_DIR", os.getcwd()),
                target_version=TargetVersion.JAVA_17,
                migration_strategy=MigrationStrategy.SPRING_BOOT
            )
            
            success = await run_migration(sessions, preferences)
            if success:
                logger.info("Migration completed successfully")
            else:
                logger.error("Migration failed")
                
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        return 1
    return 0

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Migration client stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1) 