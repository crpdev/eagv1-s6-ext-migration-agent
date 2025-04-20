from typing import Optional, Dict, Any
from pydantic import BaseModel
from models import AgentState, UserPreferences, ProjectAnalysis, MigrationPlan
from logger_config import get_logger

logger = get_logger(__name__)

class MemoryUpdate(BaseModel):
    """Represents a memory update operation"""
    state: AgentState
    update_type: str
    update_data: Dict[str, Any]

def create_initial_state(preferences: UserPreferences) -> AgentState:
    """
    Create initial agent state with user preferences.
    Pure function that creates a new state.
    """
    logger.info("Creating initial state", extra_data={"preferences": preferences.dict()})
    return AgentState(
        preferences=preferences,
        project_analysis=None,
        migration_plan=None,
        current_step=0,
        total_steps=0,
        status="initialized"
    )

def update_state_with_analysis(
    current_state: AgentState,
    analysis: ProjectAnalysis
) -> AgentState:
    """
    Create new state with updated project analysis.
    Pure function that returns a new state.
    """
    logger.info("Updating state with analysis", extra_data={"analysis": analysis.dict()})
    return AgentState(
        **current_state.dict(),
        project_analysis=analysis,
        status="analyzed"
    )

def update_state_with_plan(
    current_state: AgentState,
    plan: MigrationPlan
) -> AgentState:
    """
    Create new state with updated migration plan.
    Pure function that returns a new state.
    """
    logger.info("Updating state with plan", extra_data={"plan": plan.dict()})
    return AgentState(
        **current_state.dict(),
        migration_plan=plan,
        total_steps=len(plan.required_steps),
        status="planned"
    )

def increment_step_in_state(current_state: AgentState) -> AgentState:
    """
    Create new state with incremented step counter.
    Pure function that returns a new state.
    """
    new_step = current_state.current_step + 1
    new_status = "completed" if new_step >= current_state.total_steps else "in_progress"
    
    logger.info("Incrementing step", 
               extra_data={
                   "current_step": new_step,
                   "total_steps": current_state.total_steps,
                   "new_status": new_status
               })
    
    return AgentState(
        **current_state.dict(),
        current_step=new_step,
        status=new_status
    )

def get_state_status(state: AgentState) -> str:
    """Get the current status of the state."""
    return state.status

def is_state_initialized(state: Optional[AgentState]) -> bool:
    """Check if state is initialized."""
    return state is not None

def is_state_complete(state: AgentState) -> bool:
    """Check if state represents completed migration."""
    return state.status == "completed" 