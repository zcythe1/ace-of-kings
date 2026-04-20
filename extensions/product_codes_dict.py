import random
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class ProductCodesManager:
    TABLE_NAME = "product_codes"
    
    def __init__(self):
        self.data = self._load()
    
    def _load(self):
        """Load all product codes from Supabase"""
        try:
            response = supabase.table(self.TABLE_NAME).select("*").execute()
            # Convert to dict format: {order_id: {"key": "..."}}
            return {item["order_id"]: {"key": item["key"]} for item in response.data}
        except Exception as e:
            print(f"Error loading from Supabase: {e}")
            return {}
    
    def _sync(self, data):
        """Sync data back to Supabase"""
        # This is called after changes
        pass
    
    def generate_new_key(self):
        """Generate a new product code and store in Supabase"""
        key = ''.join(random.choices('0123456789', k=9))
        order_count = len(self.data)
        new_id = f"order-{str(order_count + 1).zfill(4)}"
        
        # Insert into Supabase
        try:
            supabase.table(self.TABLE_NAME).insert({
                "order_id": new_id,
                "key": key
            }).execute()
            
            # Update local cache
            self.data[new_id] = {"key": key}
            return new_id
        except Exception as e:
            print(f"Error generating new key: {e}")
            raise
    
    def __getitem__(self, key):
        return self.data[key]
    
    def __setitem__(self, key, value):
        self.data[key] = value
    
    def keys(self):
        return self.data.keys()
    
    def items(self):
        return self.data.items()
    
    def __len__(self):
        return len(self.data)

def make_key():
    return ''.join(random.choices('0123456789', k=9))

# Initialize the manager
valid_product_codes = ProductCodesManager()

def generate_new_key():
    return valid_product_codes.generate_new_key()