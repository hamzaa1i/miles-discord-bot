import json
import os
from pathlib import Path

class Database:
    def __init__(self, filename):
        self.filename = filename
        self.ensure_file()
    
    def ensure_file(self):
        """Create file and directory if they don't exist"""
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump({}, f)
    
    def load(self):
        """Load data from JSON file"""
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save(self, data):
        """Save data to JSON file"""
        with open(self.filename, 'w') as f:
            json.dump(data, f, indent=4)
    
    def get(self, key, default=None):
        """Get value by key"""
        data = self.load()
        return data.get(str(key), default)
    
    def set(self, key, value):
        """Set value by key"""
        data = self.load()
        data[str(key)] = value
        self.save(data)
    
    def delete(self, key):
        """Delete key"""
        data = self.load()
        if str(key) in data:
            del data[str(key)]
            self.save(data)
    
    def get_all(self):
        """Get all data"""
        return self.load()