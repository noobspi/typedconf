"""TypeSaveConfig Demo App"""
from pydantic import Field
from typesaveconfig import ConfigModel, ExportFormat



# define configuration-schema
class DbConfig(ConfigModel):
    """Config-Schema - Database Category"""
    enabled: bool = True
    loglevel: int = Field(1, description="database log-level: 0=no logging, 1=errors, 2=info")
    db_con_str:str = "db://myserver.com:1234/mydatabase"
    user:str = Field(..., description="database username")
    pwd:str = Field(..., description="database password")

class AppConfig(ConfigModel):
    """Main Configuration Schema"""
    app_name: str = "TestApp"
    tags: list[str] = Field(['tag-1', 'tag-2'], description="The tag-list.")
    db: DbConfig = Field(default_factory=DbConfig)


# MAIN
AppConfig.print_help(header=">Hello World", footer=">Good by")
conf = AppConfig.load(toml_files=['a.toml'])
if not conf:
    #AppConfig.print_help()
    exit(1)
#conf.print_config()
print(conf.export_config(ExportFormat.TOML))
