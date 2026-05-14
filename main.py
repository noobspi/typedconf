from pydantic import BaseModel, Field
from typesave_config import ConfigModel, ExportFormat




# --- Define application specific configuration  ---
class AppConfig__Prompt(BaseModel):
    name: str = Field(..., description="The name or identifier for the prompt.")
    value: int = Field(..., description="A numerical value associated with the prompt.")

class AppConfig__User(BaseModel):
    username: str = Field('anonym', description="The username.")
    password: str = Field(..., description="The password. required.")

class AppConfig(ConfigModel):
    project_name: str = Field(..., description="The name of the Python project.")
    version: str = Field(..., description="The name of the Python project.")
    user: AppConfig__User = Field(..., description="Current logged in user..")
    database_url: str = Field(..., description="The connection string for the database.")
    debug_mode: bool = Field(..., description="Indicates if debug mode is enabled.")
    allowed_hosts: list[str] = Field(..., description="A list of allowed hostnames for the application.")
    port: int = Field(..., description="The port number on which the application will run.")
    weight: float = Field(..., description="The weight of the logged in user.")
    prompts: list[AppConfig__Prompt] = Field(..., description="A list of prompt configurations.")
# --- /Define application specific configuration  ---



conf = AppConfig.load(toml_files=['test_conf.toml', 'a.toml'],
                      json_files=['a.json', 'b.json'],
                      data={'version':'0.1 alpha'},
                      load_cli=True,
                      load_env=True,
                      readonly=True,
                      )
if not conf:
    #AppConfig.print_help()
    exit(1)

conf.print_config()

print(conf.export(ExportFormat.TOML))

#console = Console()
#console.print(Pretty(conf.get_metadata()))
#print(conf.user.username, conf.user.password)
#conf.project_nameversion="OVERWRITTEN"
#conf.user.password="OVERWRITTEN"
#conf.prompts[0].name="OVERWRITTEN"
#conf.print_config()
#conf.print_help()


