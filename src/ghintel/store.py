import json, os

def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save(path, data, pretty=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, path)
