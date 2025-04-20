import google.generativeai as genai
from typing import Dict, List, Optional
from functools import partial
from logger_config import get_logger
from models import (
    UserPreferences, ProcessedInput, PreferenceQuestion,
    BudgetLevel, TravelRecommendation, Activity
)

logger = get_logger(__name__)

# Global chat session
_chat_session = None

def configure_gemini(api_key: str) -> None:
    """Configure Gemini with the provided API key."""
    logger.info("Configuring Gemini API", 
                extra_data={
                    'api_key_exists': bool(api_key),
                    'api_key_length': len(api_key) if api_key else 0
                })
    try:
        if not api_key:
            raise ValueError("API key cannot be empty")
        
        # Configure with explicit key
        genai.configure(api_key=api_key)
        
        # Verify configuration by attempting to create a model
        model = genai.GenerativeModel('gemini-pro')
        logger.debug("Successfully created Gemini model")
        
        logger.info("Gemini API configured successfully")
    except Exception as e:
        logger.error("Failed to configure Gemini API", 
                    extra_data={
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
        raise ValueError(f"Failed to configure Gemini API: {str(e)}")

def get_user_preferences() -> UserPreferences:
    """Gather initial user preferences through a structured conversation."""
    logger.info("Starting user preference collection")
    
    preferences = {}
    print("\nLet's get to know your travel preferences better!")
    
    for question in PreferenceQuestion:
        logger.debug("Asking preference question", extra_data={'question': question.value})
        answer = input(f"\n{question.value}\n> ")
        preferences[question.name.lower()] = answer
        logger.debug("Received preference answer", 
                    extra_data={'question': question.value, 'answer': answer})
    
    try:
        user_prefs = UserPreferences(
            destination_type=preferences['destination_type'],
            budget=preferences['budget'],
            activities=preferences['activities'],
            dietary_restrictions=preferences['dietary'],
            location_preference=preferences['location_type']
        )
        logger.info("Completed user preference collection", 
                    extra_data={'preferences': user_prefs.dict()})
        return user_prefs
    except Exception as e:
        logger.error("Failed to validate user preferences", 
                    extra_data={'error': str(e), 'preferences': preferences})
        raise

def create_system_prompt(preferences: UserPreferences) -> str:
    """Create a personalized system prompt based on user preferences."""
    logger.debug("Creating system prompt", extra_data={'preferences': preferences.dict()})
    
    base_prompt = """You are an intelligent travel advisor AI with expertise in creating personalized travel recommendations. 

You must always:
1. Think step-by-step about each recommendation
2. Provide structured, clear outputs
3. Separate reasoning from specific recommendations
4. Maintain context across conversations
5. Verify recommendations against user preferences
6. Identify the type of advice being given
7. Handle uncertainty by being transparent
8. Double-check all suggestions against budget and preferences
9. Only ask for clarification if absolutely necessary
10. When receiving a clarification response, provide a complete recommendation

Your responses must ALWAYS follow this EXACT format:

Destination: [Single specific location name]

Suggested Activities:
- [Activity name]: [2-3 sentence description with specific details]
- [Activity name]: [2-3 sentence description with specific details]
- [Activity name]: [2-3 sentence description with specific details]

Budget Alignment: (YES) or (NO) followed by brief explanation

Reasoning: [2-3 sentences explaining why this matches their preferences]

Current user preferences:
"""
    
    preferences_text = f"""
- Destination Type: {preferences.destination_type}
- Budget Level: {preferences.budget}
- Preferred Activities: {preferences.activities}
- Dietary Restrictions: {preferences.dietary_restrictions or 'None'}
- Location Preference: {preferences.location_preference}
"""
    prompt = base_prompt + preferences_text
    
    logger.debug("System prompt created", 
                 extra_data={'prompt_length': len(prompt)})
    return prompt

def format_response_template() -> str:
    """Return the expected response format template."""
    return """Your response must follow this exact format without any deviations:

Destination: [Single specific location name]

Suggested Activities:
- [Activity name]: [2-3 sentence description with specific details about what to expect, timing, and any special considerations]
- [Activity name]: [2-3 sentence description with specific details about what to expect, timing, and any special considerations]
- [Activity name]: [2-3 sentence description with specific details about what to expect, timing, and any special considerations]

Budget Alignment: (YES) or (NO) followed by brief explanation of how this matches their budget preferences

Reasoning: [2-3 sentences explaining specifically how this destination and activities match their stated preferences]"""

def process_input(user_input: str, 
                 context: Dict, 
                 preferences: UserPreferences,
                 is_clarification_response: bool = False) -> ProcessedInput:
    """Process user input using Gemini with context and preferences."""
    global _chat_session
    
    logger.info("Processing user input", 
                extra_data={
                    'input_length': len(user_input),
                    'context_size': len(context),
                    'preferences': preferences.dict(),
                    'is_clarification': is_clarification_response
                })
    
    system_prompt = create_system_prompt(preferences)
    logger.debug("Generated system prompt", extra_data={'system_prompt': system_prompt})
    
    try:
        # Initialize or reuse chat session
        if _chat_session is None:
            logger.debug("Initializing Gemini model and new chat session")
            model = genai.GenerativeModel('gemini-2.0-flash')
            _chat_session = model.start_chat(history=[])
            # Send system prompt only for new sessions
            logger.debug("Sending system prompt to new session")
            _chat_session.send_message(system_prompt)
            logger.debug("System prompt sent successfully")
        
        response_template = format_response_template()
        
        # Format input based on whether it's a clarification
        if is_clarification_response:
            # Get the last few interactions for context
            recent_interactions = []
            for item in list(context.values())[-3:]:  # Last 3 interactions
                if item.get('processed_input') and item.get('user_input'):
                    recent_interactions.append({
                        'query': item['user_input'],
                        'response': item['processed_input'].get('processed_input', '')
                    })
            
            # Format the context and clarification
            context_str = "\n".join(
                f"Previous query: {interaction['query']}\n"
                f"Response: {interaction['response']}\n"
                for interaction in recent_interactions
            )
            
            formatted_input = f"""Context of previous interaction:
{context_str}

You previously asked for clarification. The user has provided this additional information:
{user_input}

Based on all this information, please provide a complete and final travel recommendation. 
Do not ask for more clarifications unless absolutely necessary.

{response_template}"""
        else:
            formatted_input = f"""New user query: {user_input}

Please provide a travel recommendation based on this query and the user's preferences.
Only ask for clarification if critical information is missing.

{response_template}"""
        
        # Log the formatted input being sent to the model
        logger.debug("Sending formatted input to model", 
                    extra_data={
                        'formatted_input': formatted_input,
                        'formatted_input_length': len(formatted_input)
                    })
        
        # Send user input and get response
        response = _chat_session.send_message(formatted_input)
        response_text = response.text if response and response.text else ""
        
        # Log the response received from the model
        logger.debug("Received response from model", 
                    extra_data={
                        'model_response': response_text,
                        'response_length': len(response_text)
                    })
        
        logger.info("Successfully processed input", 
                   extra_data={'response_length': len(response_text)})
        
        return ProcessedInput(
            processed_input=response_text,
            success=bool(response_text),
            error=None if response_text else "No response received from model",
            is_clarification_response=is_clarification_response
        )
    except Exception as e:
        error_msg = str(e)
        logger.error("Failed to process input", 
                    extra_data={
                        'error': error_msg,
                        'error_type': type(e).__name__,
                        'formatted_input': formatted_input if 'formatted_input' in locals() else None
                    })
        # Reset chat session on error
        _chat_session = None
        return ProcessedInput(
            processed_input="",  # Empty string instead of None
            success=False,
            error=error_msg,
            is_clarification_response=is_clarification_response
        ) 