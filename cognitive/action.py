from typing import Optional, Dict, Any, Tuple, Callable, List
from pydantic import BaseModel
from models import MigrationPlan
from mcp import ClientSession
from logger_config import get_logger

logger = get_logger(__name__)

# Type aliases
SessionPair = Tuple[ClientSession, ClientSession]
ToolResult = Dict[str, Any]
StepExecutor = Callable[[SessionPair], bool]

class ExecutionResult(BaseModel):
    """Result of a migration step execution"""
    success: bool
    step: str
    step_index: int
    error: Optional[str] = None

async def execute_migration_step(
    sessions: SessionPair,
    plan: MigrationPlan,
    step_index: int
) -> ExecutionResult:
    """
    Execute a specific step in the migration plan.
    Pure function that takes sessions and plan and returns execution result.
    """
    try:
        if step_index >= len(plan.required_steps):
            return ExecutionResult(
                success=False,
                step="invalid",
                step_index=step_index,
                error="Invalid step index"
            )
            
        step = plan.required_steps[step_index]
        logger.info("Executing migration step", 
                   extra_data={"step": step, "step_index": step_index})
        
        executor = get_step_executor(step)
        if not executor:
            return ExecutionResult(
                success=False,
                step=step,
                step_index=step_index,
                error=f"Unknown step type: {step}"
            )
            
        success = await executor(sessions)
        
        result = ExecutionResult(
            success=success,
            step=step,
            step_index=step_index
        )
        
        log_execution_result(result)
        return result
        
    except Exception as e:
        error_msg = f"Error executing migration step: {str(e)}"
        logger.error(error_msg)
        return ExecutionResult(
            success=False,
            step=plan.required_steps[step_index],
            step_index=step_index,
            error=error_msg
        )

def get_step_executor(step: str) -> Optional[StepExecutor]:
    """Get the appropriate executor function for a step."""
    step_executors: Dict[str, StepExecutor] = {
        "Update Java version": update_java_version,
        "Update Spring Boot version": update_spring_boot,
        "Update dependencies": update_dependencies,
        "Refactor code": refactor_code
    }
    return step_executors.get(step)

def log_execution_result(result: ExecutionResult) -> None:
    """Log the result of step execution."""
    if result.success:
        logger.info("Migration step completed successfully", 
                   extra_data={"step": result.step})
    else:
        logger.error("Migration step failed", 
                    extra_data={
                        "step": result.step,
                        "error": result.error
                    })

async def update_java_version(sessions: SessionPair) -> bool:
    """
    Update Java version using Maven tools.
    Pure function that takes sessions and returns success status.
    """
    try:
        _, maven_session = sessions
        result = await maven_session.call_tool("mod_build_all")
        return result is not None
    except Exception as e:
        logger.error(f"Error updating Java version: {str(e)}")
        return False

async def update_spring_boot(sessions: SessionPair) -> bool:
    """
    Update Spring Boot version using Moderne tools.
    Pure function that takes sessions and returns success status.
    """
    try:
        moderne_session, _ = sessions
        
        # Apply upgrade recipe
        upgrade_result = await moderne_session.call_tool(
            "mod_upgrade_all",
            {"text": "UpgradeSpringBoot_3_2"}
        )
        
        if not upgrade_result:
            return False
            
        # Apply changes
        apply_result = await moderne_session.call_tool("mod_apply_upgrade_all")
        return apply_result is not None
        
    except Exception as e:
        logger.error(f"Error updating Spring Boot: {str(e)}")
        return False

async def update_dependencies(sessions: SessionPair) -> bool:
    """
    Update project dependencies.
    Pure function that takes sessions and returns success status.
    """
    try:
        _, maven_session = sessions
        result = await maven_session.call_tool("mod_build_all")
        return result is not None
    except Exception as e:
        logger.error(f"Error updating dependencies: {str(e)}")
        return False

async def refactor_code(sessions: SessionPair) -> bool:
    """
    Refactor code using Moderne tools.
    Pure function that takes sessions and returns success status.
    """
    try:
        moderne_session, _ = sessions
        result = await moderne_session.call_tool("mod_apply_upgrade_all")
        return result is not None
    except Exception as e:
        logger.error(f"Error refactoring code: {str(e)}")
        return False 