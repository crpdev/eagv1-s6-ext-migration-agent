from typing import Dict, List, Optional, Callable
from decision_making import DecisionType, Decision

def create_response_templates() -> Dict[DecisionType, Callable[[Decision], str]]:
    """Create a mapping of decision types to their formatting functions."""
    return {
        DecisionType.RECOMMENDATION: format_recommendation,
        DecisionType.CLARIFICATION: format_clarification,
        DecisionType.ERROR: format_error,
        DecisionType.REFINEMENT: format_refinement
    }

def execute(decision: Decision) -> Dict:
    """Execute the decision and generate appropriate response."""
    templates = create_response_templates()
    formatter = templates.get(decision.decision_type, format_error)
    response = formatter(decision)
    
    return {
        "response": response,
        "success": decision.decision_type != DecisionType.ERROR,
        "metadata": {
            "decision_type": decision.decision_type.value,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning
        }
    }

def format_recommendation(decision: Decision) -> str:
    """Format a travel recommendation response."""
    recommendation = decision.action
    
    response_parts = [
        "Based on your preferences, here's my recommendation:",
        f"\nDestination: {recommendation['destination']}",
        "\nSuggested Activities:"
    ]
    
    activities = recommendation.get("activities", [])
    response_parts.extend(f"- {activity}" for activity in activities)
    
    response_parts.extend([
        f"\nBudget Alignment: {'✓' if recommendation['budget_alignment'] else '✗'}",
        f"\nReasoning: {decision.reasoning}"
    ])
    
    if decision.confidence < 0.8:
        response_parts.append(
            "\nNote: This is a preliminary recommendation. "
            "I can provide more targeted suggestions with additional information."
        )
        
    return "\n".join(response_parts)

def format_clarification(decision: Decision) -> str:
    """Format a clarification request."""
    return (f"I need some additional information to better assist you:\n"
            f"{decision.action['request']}")

def format_error(decision: Decision) -> str:
    """Format an error response."""
    return (f"I apologize, but I encountered an issue: "
            f"{decision.action.get('error_message', 'Unknown error')}\n"
            f"Please try again or rephrase your request.")

def format_refinement(decision: Decision) -> str:
    """Format refinement suggestions."""
    suggestions = decision.action["suggestions"]
    
    response_parts = [
        "To provide better recommendations, could you please help me understand:",
        ""
    ]
    
    response_parts.extend(f"- {suggestion}" for suggestion in suggestions)
    return "\n".join(response_parts)

def log_action(action_result: Dict) -> None:
    """Log the action result for monitoring and improvement."""
    metadata = action_result["metadata"]
    print(f"Action executed: {metadata['decision_type']}")
    print(f"Confidence: {metadata['confidence']}")
    print(f"Success: {action_result['success']}")
    print(f"Reasoning: {metadata['reasoning']}") 