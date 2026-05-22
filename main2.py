"""TypedConf Demo App"""
from pydantic import Field, ValidationError
from typedconf import ConfigModel, ConfigError



# define configuration-schema
class DbConfig(ConfigModel):
    """Config-Schema - Database Category"""
    enabled: bool = True
    db_con_str:str = "db://myserver.com:1234/mydatabase"
    user:str = Field("anonym", description="database username")
    pwd:str = Field("secret", description="database password")
    loglevel: int = Field(..., description="database log-level: 0=no logging, 1=errors, 2=info")

class AppConfig(ConfigModel):
    """Main Configuration Schema"""
    app_name: str
    tags: list[str] = Field(['tag-1', 'tag-2'], description="The tag list.")
    db: DbConfig = Field(default_factory=DbConfig, description="database configuration")



# MAIN
if AppConfig.user_needs_help():
    print("MYAPP\n", AppConfig.get_cli_helptext())
    exit(0)

try:
    conf = AppConfig.load(toml_files=['a.toml'], readonly=False)
    conf.app_name = "XXX"    # RAISES ERROR
    print(conf.dumps_json() )
except (ConfigError, ValidationError) as e:
    print(e)
