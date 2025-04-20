from typing import Dict, List, Optional, Tuple, NamedTuple
from enum import Enum
from functools import partial

class DecisionType(Enum):
    RECOMMENDATION = "recommendation"
    CLARIFICATION = "clarification"
    ERROR = "error"
    REFINEMENT = "refinement"

class Decision(NamedTuple):
    """Immutable decision container."""
    decision_type: DecisionType
    action: Dict
    confidence: float
    reasoning: str

CONFIDENCE_THRESHOLD = 0.7

def analyze_input(processed_input: Dict,
                 context: List[Dict],
                 preferences: Dict[str, str]) -> Decision:
    """Analyze processed input and make decisions."""
    if not processed_input["success"]:
        return handle_error(processed_input["error"])
        
    return evaluate_response(
        processed_input["processed_input"],
        context,
        preferences
    )

def evaluate_response(response: str,
                     context: List[Dict],
                     preferences: Dict[str, str]) -> Decision:
    """Evaluate the response and determine next action."""
    # First check if the response contains actual recommendations
    recommendation = generate_recommendation(response, preferences)
    
    # If we have a valid recommendation with good confidence, return it
    if (recommendation["confidence"] >= CONFIDENCE_THRESHOLD and 
        recommendation["is_valid_recommendation"]):
        return Decision(
            DecisionType.RECOMMENDATION,
            recommendation,
            recommendation["confidence"],
            recommendation["reasoning"]
        )
    
    # Check if the response is asking for clarification
    clarification_indicators = [
        "could you please clarify",
        "need more information",
        "please specify",
        "could you tell me more",
        "would you mind sharing",
        "can you provide more details",
        "what kind of",
        "what type of",
        "could you elaborate"
    ]
    
    response_lower = response.lower()
    is_asking_clarification = any(indicator in response_lower 
                                for indicator in clarification_indicators)
    
    # If we're already in a clarification state (check context)
    if context and any(item.get('processed_input', {}).get('is_clarification_response', False) 
                      for item in context):
        # Force a recommendation even with low confidence
        return Decision(
            DecisionType.RECOMMENDATION,
            recommendation,
            max(recommendation["confidence"], CONFIDENCE_THRESHOLD),  # Force confidence up
            "Providing recommendation based on available information"
        )
    
    # Only ask for clarification if explicitly needed and not in a clarification chain
    if is_asking_clarification and needs_clarification(response, preferences):
        return Decision(
            DecisionType.CLARIFICATION,
            {"request": generate_clarification_request(response, preferences)},
            0.8,
            "Additional information needed for accurate recommendation"
        )
    
    # Default to recommendation with current information
    return Decision(
        DecisionType.RECOMMENDATION,
        recommendation,
        recommendation["confidence"],
        recommendation["reasoning"]
    )

def needs_clarification(response: str, preferences: Dict[str, str]) -> bool:
    """Determine if clarification is needed."""
    # If we already have basic preferences, don't ask for clarification
    if preferences and len(preferences) >= 3:
        return False
    
    # Only check for truly missing critical information
    required_preferences = {
        "destination type",
        "budget",
        "activities"
    }
    
    # Check both preferences and the current response
    combined_text = str(preferences).lower() + " " + response.lower()
    missing_prefs = [pref for pref in required_preferences 
                    if pref not in combined_text]
    
    # Check if the response already contains specific recommendations
    contains_specific_info = any(indicator in response.lower() for indicator in [
        "hotel",
        "restaurant",
        "attraction",
        "destination",
        "city",
        "country",
        "place",
        "location"
    ])
    
    # If we have specific recommendations, don't ask for clarification
    if contains_specific_info:
        return False
    
    # Only ask for clarification if multiple critical pieces are missing
    # and we don't have specific recommendations
    return len(missing_prefs) > 1

def generate_clarification_request(response: str, preferences: Dict[str, str]) -> str:
    """Generate a clarification request based on missing information."""
    missing_info = []
    if "destination type" not in str(preferences).lower():
        missing_info.append("preferred type of destination")
    if "budget" not in str(preferences).lower():
        missing_info.append("travel budget")
    if "activities" not in str(preferences).lower():
        missing_info.append("preferred activities")
        
    return f"Please provide more information about your {', '.join(missing_info)}"

def generate_recommendation(response: str, preferences: Dict[str, str]) -> Dict:
    """Generate a travel recommendation based on preferences."""
    # Extract key information from the response
    destination = extract_destination(response)
    activities = extract_activities(response, preferences)
    budget_alignment = check_budget_alignment(response, preferences)
    
    # Calculate confidence and check validity
    confidence = calculate_confidence(response, preferences)
    
    # Check if this is a valid recommendation
    is_valid = bool(
        destination and 
        destination.lower() not in ["okay", "well", "so", "i", "the", "a", "an", "this"] and
        len(activities) > 0 and
        not any(word in destination.lower() for word in ["clarify", "specify", "tell", "share"])
    )
    
    # Generate appropriate reasoning
    if is_valid:
        reasoning = generate_reasoning(response, preferences)
    else:
        # Try to extract a better destination if the first one wasn't valid
        alternative_destinations = [
            word for word in response.split() 
            if word[0].isupper() and 
            word.lower() not in ["i", "okay", "well", "so", "the", "a", "an", "this"] and
            len(word) > 2
        ]
        destination = alternative_destinations[0] if alternative_destinations else "Unknown Location"
        reasoning = "Based on the available information, here's a suggested destination and activities."
    
    return {
        "destination": destination,
        "activities": activities,
        "budget_alignment": budget_alignment,
        "confidence": confidence,
        "reasoning": reasoning,
        "is_valid_recommendation": is_valid
    }

def calculate_confidence(response: str, preferences: Dict[str, str]) -> float:
    """Calculate confidence score for the recommendation."""
    score = 0.5  # Base score
    
    if preferences.get("budget", "").lower() in response.lower():
        score += 0.2
    if preferences.get("destination type", "").lower() in response.lower():
        score += 0.2
    if preferences.get("activities", "").lower() in response.lower():
        score += 0.1
        
    return min(score, 1.0)

def handle_error(error: str) -> Decision:
    """Handle error cases."""
    return Decision(
        DecisionType.ERROR,
        {"error_message": f"An error occurred: {error}"},
        0.0,
        "Error in processing request"
    )

def generate_refinement_suggestions(response: str, preferences: Dict[str, str]) -> List[str]:
    """Generate suggestions for refining the request."""
    return [
        "Could you specify your preferred travel season?",
        "How long would you like to stay?",
        "Are you traveling alone or with others?",
        "Do you have any specific must-see attractions in mind?"
    ]

def extract_destination(response: str) -> str:
    """Extract destination from response."""
    # Look for destination after common markers
    destination_markers = [
        "Destination:",
        "I recommend",
        "you should visit",
        "consider visiting",
        "suggest",
        "perfect destination would be",
        "recommend visiting"
    ]
    
    response_lines = response.split('\n')
    
    # First try to find destination after markers
    for line in response_lines:
        for marker in destination_markers:
            if marker.lower() in line.lower():
                # Get text after the marker
                text_after = line[line.lower().index(marker.lower()) + len(marker):].strip()
                # Split into words and look for capitalized location names
                words = text_after.split()
                for i, word in enumerate(words):
                    # Check for capitalized words that could be place names
                    if (word[0].isupper() and 
                        len(word) > 2 and 
                        word.lower() not in ["i", "this", "the", "a", "an", "you", "your"]):
                        # If next word is also capitalized, include it (e.g., "New York")
                        if (i + 1 < len(words) and 
                            words[i + 1][0].isupper() and 
                            words[i + 1].lower() not in ["i", "this", "the", "a", "an"]):
                            return f"{word} {words[i + 1]}"
                        return word
    
    # If no destination found with markers, look for any capitalized words
    # that might be place names
    for line in response_lines:
        words = line.split()
        for i, word in enumerate(words):
            if (word[0].isupper() and 
                len(word) > 2 and 
                word.lower() not in ["i", "this", "the", "a", "an", "you", "your"]):
                # Check for multi-word place names
                if (i + 1 < len(words) and 
                    words[i + 1][0].isupper() and 
                    words[i + 1].lower() not in ["i", "this", "the", "a", "an"]):
                    return f"{word} {words[i + 1]}"
                return word
    
    return ""

def extract_activities(response: str, preferences: Dict[str, str]) -> List[str]:
    """Extract suggested activities from response."""
    activities = []
    in_activities_section = False
    current_activity = []
    
    # Split response into lines
    lines = response.split('\n')
    
    for line in lines:
        # Check if we're entering the activities section
        if "Suggested Activities:" in line or "Activities:" in line:
            in_activities_section = True
            continue
        
        # Check if we're leaving the activities section
        if in_activities_section and (line.strip().startswith("Budget") or not line.strip()):
            in_activities_section = False
        
        # Process lines in the activities section
        if in_activities_section and line.strip():
            # Clean up the line
            cleaned_line = line.strip()
            if cleaned_line.startswith('- ') or cleaned_line.startswith('* '):
                # If we had a previous activity, add it
                if current_activity:
                    activities.append(' '.join(current_activity))
                    current_activity = []
                # Start new activity
                cleaned_line = cleaned_line[2:].strip()
                
            # Remove markdown formatting
            cleaned_line = cleaned_line.replace('**', '').replace('*', '')
            
            # Add to current activity
            if cleaned_line:
                current_activity.append(cleaned_line)
    
    # Add the last activity if exists
    if current_activity:
        activities.append(' '.join(current_activity))
    
    # If no activities found in the structured format, try extracting from the whole text
    if not activities:
        # Look for activity indicators
        activity_indicators = [
            "you can",
            "try",
            "enjoy",
            "experience",
            "visit",
            "explore",
            "participate in"
        ]
        
        for line in response.split('.'):
            for indicator in activity_indicators:
                if indicator in line.lower():
                    activity = line.strip()
                    if activity and len(activity) > 10:  # Minimum length to be meaningful
                        activities.append(activity)
    
    # Clean up activities
    cleaned_activities = []
    for activity in activities:
        # Remove common prefixes
        activity = activity.strip()
        activity = activity.replace('you can ', '')
        activity = activity.replace('you could ', '')
        activity = activity.replace('we recommend ', '')
        # Capitalize first letter
        if activity:
            activity = activity[0].upper() + activity[1:]
            cleaned_activities.append(activity)
    
    return cleaned_activities

def check_budget_alignment(response: str, preferences: Dict[str, str]) -> bool:
    """Check if recommendation aligns with budget preferences."""
    budget = preferences.get("budget", "").lower()
    return budget in response.lower()

def generate_reasoning(response: str, preferences: Dict[str, str]) -> str:
    """Generate reasoning for the recommendation."""
    return (f"Based on your preferences for {preferences.get('destination type', 'unknown')} destinations "
            f"and {preferences.get('activities', 'various activities')}, "
            f"with a {preferences.get('budget', 'flexible')} budget.") 