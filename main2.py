"""TypedConf Demo App"""
from pydantic import Field, ValidationError
from typedconf import ConfigModel, ConfigError, UserNeedsHelp


RFC3986_URI_REGEX = r'^([a-zA-Z][a-zA-Z0-9+.-]*:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})(?::\d+)?([\/\w \.-]*)*\/?$'

# define configuration-schema
class DbConfig(ConfigModel):
    """Config-Schema - Database Category"""
    enabled: bool = True
    con:str = Field("db://myserver.com:1234/mydatabase", pattern=RFC3986_URI_REGEX)
    user:str = Field("anonym", description="database username")
    pwd:str = Field("secret", description="database password")
    loglevel: int = Field(..., description="database log-level: 0=no logging, 1=errors, 2=info")

class AppConfig(ConfigModel):
    """Main Configuration Schema"""
    app_name: str
    tags: list[str] = Field(['tag-1', 'tag-2'], description="The tag list")
    db: DbConfig = Field(default_factory=DbConfig, description="database configuration") # type: ignore



# MAIN
# if AppConfig.user_needs_help():
#     print(f"MYAPP called Help activly\n{AppConfig.get_cli_helptext()}")
#     exit(0)
conf:AppConfig

try:
    conf = AppConfig.load(
        payload={'app_name':'myapp', 'db':{'loglevel':1}},
        toml_files=['a.toml'],
        cli_prefix='pre_',
        cli_help_enabled=True,
    )
    print("config loaded:\n", conf.dumps_json(), "\n=====================\n")

    #TODO: Re-Think "writeable": Do the user need a writeable config?!
    # conf.app_name = "raise readonly-error app"  # ok
    # conf.db.user  = "raise readonly-error user" # not ok. nested model-config for RwConfigModel only works for root-model/instance. not for the nested ones!


except (ConfigError, ValidationError) as e:
    print(e)
except UserNeedsHelp as h:
    print(f"MYAPP called Help passive via try/except\n{h}")
    exit(0)


# try:
#     conf.app_name = "XYZ-APP"    # RAISES ValidationError when readonly
#     #conf.db.con = ":no-valid-url:" # RAISES pattern-matching
#     conf.db.con = "db://myserver.com/mydatabase"

#     print(conf.dumps_json())
# except ValidationError as e:
#     print(e)