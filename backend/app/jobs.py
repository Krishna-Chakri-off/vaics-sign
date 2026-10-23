import json
from .services.jobs import run_all

if __name__ == "__main__":
    print(json.dumps(run_all()))
