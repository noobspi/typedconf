from pydantic import Field
from typesaveconfig import ConfigModel, ExportFormat


# define configuration-schema
class SubConfig(ConfigModel):
    """Config-Schema - Sub Category"""
    enabled: bool = True
    level: int = 1

class AppConfig(ConfigModel):
    """Main Configuration Schema"""
    app_name: str = "TestApp"
    port: int = Field(22, description="The port number on which the xc<xcfds<furbzEIURBZuirzuiN application will run.")
    tags: list[str] = Field(['tag-1', 'tag-2'], description="The tag-list.")
    sub: SubConfig = Field(default_factory=SubConfig)

print(AppConfig.get_helptext())


conf = AppConfig.load(toml_files=['a.toml'])
if not conf:
    #AppConfig.print_help()
    exit(1)
#conf.print_config()
print(conf.export_config(ExportFormat.TOML))

