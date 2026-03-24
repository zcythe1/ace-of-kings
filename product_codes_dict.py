import random
import json
import os

STORE = "product_codes.json"

def make_key():
    return ''.join(random.choices('0123456789', k=9))

def _load():
    if os.path.exists(STORE):
        with open(STORE) as f:
            return json.load(f)
    defaults = {
        "order-0001": {"key": make_key()},
        "arka-key":   {"key": make_key()}
    }
    _save(defaults)
    return defaults

def _save(data):
    with open(STORE, "w") as f:
        json.dump(data, f, indent=2)

valid_product_codes = _load()

def generate_new_key():
    l = len(valid_product_codes)
    new_id = f"ordker-{str(l + 1).zfill(4)}"
    valid_product_codes[new_id] = {"key": make_key()}
    _save(valid_product_codes)
    return new_id