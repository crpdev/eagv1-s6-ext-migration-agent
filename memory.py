from typing import Dict, List, Optional, NamedTuple
import json
from datetime import datetime
from copy import deepcopy

class MemoryState(NamedTuple):
    """Immutable memory state container."""
    conversation_history: List[Dict]
    user_preferences: Dict[str, str]
    recommendations: List[Dict]

def create_memory_state() -> MemoryState:
    """Create a new memory state."""
    return MemoryState([], {}, [])

def store_preferences(state: MemoryState, preferences: Dict[str, str]) -> MemoryState:
    """Store user preferences in memory."""
    return MemoryState(
        state.conversation_history,
        preferences,
        state.recommendations
    )

def add_to_history(state: MemoryState, entry: Dict) -> MemoryState:
    """Add a new conversation entry to history."""
    new_entry = deepcopy(entry)
    new_entry["timestamp"] = datetime.now().isoformat()
    
    return MemoryState(
        state.conversation_history + [new_entry],
        state.user_preferences,
        state.recommendations
    )

def get_recent_context(state: MemoryState, n_entries: int = 5) -> List[Dict]:
    """Get the n most recent conversation entries."""
    return state.conversation_history[-n_entries:]

def store_recommendation(state: MemoryState, recommendation: Dict) -> MemoryState:
    """Store a travel recommendation."""
    new_recommendation = deepcopy(recommendation)
    new_recommendation["timestamp"] = datetime.now().isoformat()
    
    return MemoryState(
        state.conversation_history,
        state.user_preferences,
        state.recommendations + [new_recommendation]
    )

def get_relevant_recommendations(state: MemoryState, query: str) -> List[Dict]:
    """Get recommendations relevant to the query."""
    query_keywords = query.lower().split()
    return [
        rec for rec in state.recommendations
        if any(keyword in rec.get("description", "").lower() 
              for keyword in query_keywords)
    ]

def get_preferences(state: MemoryState) -> Dict[str, str]:
    """Retrieve stored user preferences."""
    return state.user_preferences

def save_to_file(state: MemoryState, filename: str = "memory_backup.json") -> None:
    """Save memory state to a file."""
    memory_dict = {
        "preferences": state.user_preferences,
        "history": state.conversation_history,
        "recommendations": state.recommendations
    }
    
    with open(filename, 'w') as f:
        json.dump(memory_dict, f, indent=2)

def load_from_file(filename: str = "memory_backup.json") -> Optional[MemoryState]:
    """Load memory state from a file."""
    try:
        with open(filename, 'r') as f:
            memory_dict = json.load(f)
            
        return MemoryState(
            memory_dict.get("history", []),
            memory_dict.get("preferences", {}),
            memory_dict.get("recommendations", [])
        )
    except Exception:
        return None 