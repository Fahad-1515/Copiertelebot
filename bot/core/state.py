from typing import Dict, Optional

class UserState:
    def __init__(self):
        self.states: Dict[int, str] = {}
        self.data: Dict[int, Dict] = {}
    
    def set_state(self, user_id: int, state: str):
        self.states[user_id] = state
        if user_id not in self.data:
            self.data[user_id] = {}
    
    def get_state(self, user_id: int) -> Optional[str]:
        return self.states.get(user_id)
    
    def set_data(self, user_id: int, key: str, value: any):
        if user_id not in self.data:
            self.data[user_id] = {}
        self.data[user_id][key] = value
    
    def get_data(self, user_id: int, key: str) -> any:
        return self.data.get(user_id, {}).get(key)
    
    def clear_state(self, user_id: int):
        if user_id in self.states:
            del self.states[user_id]
        if user_id in self.data:
            del self.data[user_id]
    
    def update_data(self, user_id: int, updates: Dict):
        if user_id not in self.data:
            self.data[user_id] = {}
        self.data[user_id].update(updates)

user_states = UserState()