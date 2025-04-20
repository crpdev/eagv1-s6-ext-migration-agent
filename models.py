from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field, validator
from datetime import datetime

class PreferenceQuestion(str, Enum):
    DESTINATION_TYPE = "What type of destinations do you prefer (urban/nature/beach/etc.)?"
    BUDGET = "What's your preferred travel budget (budget/moderate/luxury)?"
    ACTIVITIES = "What activities interest you most while traveling?"
    DIETARY = "Any dietary restrictions or preferences?"
    LOCATION_TYPE = "Do you prefer popular tourist spots or off-the-beaten-path locations?"

class BudgetLevel(str, Enum):
    BUDGET = "budget"
    MODERATE = "moderate"
    LUXURY = "luxury"

class DecisionType(str, Enum):
    RECOMMENDATION = "recommendation"
    CLARIFICATION = "clarification"
    ERROR = "error"
    REFINEMENT = "refinement"

class MigrationStrategy(str, Enum):
    JAVA = "java"
    SPRING_BOOT = "spring_boot"

class TargetVersion(str, Enum):
    JAVA_8 = "java_8"
    JAVA_11 = "java_11"
    JAVA_17 = "java_17"
    JAVA_21 = "java_21"
    SPRING_BOOT_2_7 = "spring_boot_2_7"
    SPRING_BOOT_3_0 = "spring_boot_3_0"
    SPRING_BOOT_3_2 = "spring_boot_3_2"

class UserPreferences(BaseModel):
    destination_type: str = Field(..., description="User's preferred type of destinations")
    budget: BudgetLevel = Field(..., description="User's travel budget level")
    activities: str = Field(..., description="Preferred activities while traveling")
    dietary_restrictions: Optional[str] = Field(None, description="Any dietary restrictions")
    location_preference: str = Field(..., description="Preference for tourist spots vs off-beaten-path")
    project_directory: str = Field(..., description="Path to the project directory")
    migration_strategy: MigrationStrategy = Field(..., description="Migration strategy to use")
    target_version: TargetVersion = Field(..., description="Target version type")

    @validator('budget', pre=True)
    def validate_budget(cls, v):
        if isinstance(v, str):
            v = v.lower()
            if v in [b.value for b in BudgetLevel]:
                return v
            raise ValueError(f"Invalid budget level. Must be one of: {[b.value for b in BudgetLevel]}")
        return v

class Activity(BaseModel):
    name: str = Field(..., description="Name of the activity")
    description: str = Field(..., description="Detailed description of the activity")
    duration: Optional[str] = Field(None, description="Expected duration of the activity")
    considerations: Optional[str] = Field(None, description="Special considerations for the activity")

class TravelRecommendation(BaseModel):
    destination: str = Field(..., description="Name of the recommended destination")
    activities: List[Activity] = Field(..., min_items=1, max_items=5, description="List of recommended activities")
    budget_alignment: bool = Field(..., description="Whether recommendation aligns with budget")
    budget_explanation: str = Field(..., description="Explanation of budget alignment")
    reasoning: str = Field(..., description="Reasoning behind the recommendation")
    timestamp: datetime = Field(default_factory=datetime.now)

class ProcessedInput(BaseModel):
    processed_input: str = Field(..., description="Processed text from the model")
    success: bool = Field(..., description="Whether processing was successful")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    is_clarification_response: bool = Field(..., description="Whether this is a clarification response")

class Decision(BaseModel):
    decision_type: DecisionType
    action: Dict = Field(..., description="Action details based on decision type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the decision")
    reasoning: str = Field(..., description="Reasoning behind the decision")

class Interaction(BaseModel):
    user_input: str = Field(..., description="Original user input")
    processed_input: ProcessedInput = Field(..., description="Processed input details")
    decision: Decision = Field(..., description="Decision made based on input")
    action_result: Dict = Field(..., description="Result of executing the decision")
    timestamp: datetime = Field(default_factory=datetime.now)

class MemoryState(BaseModel):
    user_preferences: UserPreferences = Field(..., description="User's stored preferences")
    interaction_history: List[Interaction] = Field(default_factory=list, description="History of interactions")
    last_interaction_time: datetime = Field(default_factory=datetime.now)

class ProjectAnalysis(BaseModel):
    java_version: str
    spring_boot_version: Optional[str]
    dependencies: Dict[str, str]
    build_tool: str
    
class MigrationPlan(BaseModel):
    current_state: ProjectAnalysis
    target_state: ProjectAnalysis
    required_steps: List[str]
    estimated_effort: str
    
class MigrationPreferences(BaseModel):
    project_directory: str = Field(..., description="Path to the project directory")
    migration_strategy: MigrationStrategy = Field(..., description="Migration strategy to use")
    target_version: TargetVersion = Field(..., description="Target version type")

class AgentState(BaseModel):
    preferences: MigrationPreferences
    project_analysis: Optional[ProjectAnalysis] = None
    migration_plan: Optional[MigrationPlan] = None
    current_step: int = 0
    total_steps: int = 0
    status: str = "initialized"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        } 