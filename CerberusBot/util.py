import json

def load_config():
    json_string = ""
    with open("config.json") as file:
        json_string = file.read()
    config = json.loads(json_string)
    return config
