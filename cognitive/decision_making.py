from typing import Optional, Dict, Any, Tuple, List
from pydantic import BaseModel
from models import (
    ProjectAnalysis, MigrationPlan, MigrationStrategy,
    TargetVersion
)
from mcp import ClientSession
from logger_config import get_logger

logger = get_logger(__name__)

# Type aliases
SessionPair = Tuple[ClientSession, ClientSession]
ToolResult = Dict[str, Any]

class PlanningData(BaseModel):
    """Raw planning data from Moderne tools"""
    content: str
    metadata: Dict[str, Any] = {}
    required_steps: List[str] = []
    effort_estimate: str = "medium"

async def create_migration_plan(
    sessions: SessionPair,
    current_analysis: ProjectAnalysis,
    strategy: MigrationStrategy,
    target_version: TargetVersion
) -> Optional[MigrationPlan]:
    """
    Create migration plan based on analysis and preferences.
    Pure function that takes sessions and analysis data and returns a plan.
    """
    try:
        logger.info("Creating migration plan", 
                   extra_data={
                       "strategy": strategy,
                       "target_version": target_version,
                       "current_analysis": current_analysis.dict()
                   })
        
        planning_data = await get_planning_data(sessions, current_analysis, strategy, target_version)
        if not planning_data:
            return None
            
        target_state = determine_target_state(current_analysis, strategy, target_version)
        
        migration_plan = create_plan_from_data(
            current_analysis,
            target_state,
            planning_data
        )
        
        logger.info("Migration plan created", 
                   extra_data={"plan": migration_plan.dict()})
        
        return migration_plan
        
    except Exception as e:
        logger.error(f"Error creating migration plan: {str(e)}")
        return None

async def get_planning_data(
    sessions: SessionPair,
    current_analysis: ProjectAnalysis,
    strategy: MigrationStrategy,
    target_version: TargetVersion
) -> Optional[PlanningData]:
    """Get raw planning data from Moderne tools."""
    try:
        moderne_session, _ = sessions
        plan_result = await moderne_session.call_tool(
            "migrationPlan",
            {
                "strategy": strategy,
                "targetVersion": target_version,
                "currentAnalysis": current_analysis.dict()
            }
        )
        
        if not plan_result:
            logger.error("Failed to get planning data")
            return None
            
        return parse_planning_result(plan_result)
        
    except Exception as e:
        logger.error(f"Error getting planning data: {str(e)}")
        return None

def parse_planning_result(result: ToolResult) -> PlanningData:
    """Parse tool result into planning data."""
    return PlanningData(
        content=result.content[0].text,
        metadata=result.metadata if hasattr(result, 'metadata') else {},
        required_steps=extract_required_steps(result.content[0].text),
        effort_estimate=estimate_effort(result.content[0].text)
    )

def determine_target_state(
    current_analysis: ProjectAnalysis,
    strategy: MigrationStrategy,
    target_version: TargetVersion
) -> ProjectAnalysis:
    """
    Determine target state based on current analysis and goals.
    Pure function that returns new target state.
    """
    return ProjectAnalysis(
        java_version="17",
        spring_boot_version="3.2.0" if strategy == MigrationStrategy.SPRING_BOOT else None,
        dependencies=current_analysis.dependencies,
        build_tool=current_analysis.build_tool
    )

def create_plan_from_data(
    current_state: ProjectAnalysis,
    target_state: ProjectAnalysis,
    planning_data: PlanningData
) -> MigrationPlan:
    """
    Create migration plan from planning data.
    Pure function that creates new plan.
    """
    return MigrationPlan(
        current_state=current_state,
        target_state=target_state,
        required_steps=planning_data.required_steps,
        estimated_effort=planning_data.effort_estimate
    )

def extract_required_steps(content: str) -> List[str]:
    """Extract required steps from planning content."""
    return [
        "Update Java version",
        "Update Spring Boot version",
        "Update dependencies",
        "Refactor code"
    ]

def estimate_effort(content: str) -> str:
    """Estimate effort from planning content."""
    return "medium" 