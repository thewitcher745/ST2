from dotenv import dotenv_values


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)

        return cls._instance

    def __init__(self, env_file_path: str = ".env.config"):
        config_values = dotenv_values(env_file_path)

        for key, value in config_values.items():
            self.__setattr__(key, value)

    def __repr__(self):
        output = "Current config:\n"
        for key, value in self.__dict__.items():
            output += f"\t{key}: {value}\n"

        return output
