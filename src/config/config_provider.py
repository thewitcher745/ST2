from dotenv import dotenv_values


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)

        return cls._instance

    def __init__(
        self,
        config_env_path: str = ".env.config",
        misc_env_path: str = ".env.misc",
        misc_local_env_path: str = ".env.misc.local",
        secret_env_path: str = ".env.secret",
    ):
        config_values = dotenv_values(config_env_path)
        misc_values = dotenv_values(misc_env_path)
        misc_local_values = dotenv_values(misc_local_env_path)
        secret_values = dotenv_values(secret_env_path)

        for key, value in config_values.items():
            self.__setattr__(key, value)

        for key, value in misc_values.items():
            self.__setattr__(key, value)

        for key, value in secret_values.items():
            self.__setattr__(key, value)

        for key, value in misc_local_values.items():
            self.__setattr__(key, value)

    def __repr__(self):
        output = "Current config:\n"
        for key, value in self.__dict__.items():
            output += f"\t{key}: {value}\n"

        return output

    def get(self, param_label: str) -> str:
        try:
            return getattr(self, param_label)
        except AttributeError:
            raise

    def get_optional(self, param_label: str) -> str | None:
        try:
            return getattr(self, param_label)
        except AttributeError:
            return None
