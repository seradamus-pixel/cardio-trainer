# Configuration Manager

class ConfigManager:
    def __init__(self, config_file):
        self.config_file = config_file

    def load_config(self):
        with open(self.config_file, 'r') as file:
            return json.load(file)

    def save_config(self, config_data):
        with open(self.config_file, 'w') as file:
            json.dump(config_data, file)

# Example usage
# config_manager = ConfigManager('path/to/config.json')
# config = config_manager.load_config()