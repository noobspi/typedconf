# TypedConf

A lightweight, type-safe configuration management library powered by Pydantic.
Following the [12-factor application guide](https://12factor.net/config), it centralizes your application configuration/settings
by merging data from multiple sources with a defined priority: `ENV > CLI > JSON > TOML > Payload > Default`.

Heavily inspired by
[dynaconf](https://www.dynaconf.com/),
[pydantic](https://pydantic.dev/docs/validation/latest/get-started/) and
[fastapi](https://fastapi.tiangolo.com/python-types/).

## Key Features

- **Type-Safe:** Built on Pydantic, ensuring configuration values are validated at runtime.
- **IDE Support:** Full type-hinting and IntelliSense-Support for seamless development.
- **Nested Support:** Easily handle complex configuration structures.
- **TOML and JSON Interface:** Load configuration from toml and/or json files.
- **CLI and Environment Interface:** Load configuration data from CLI interface (--cfg_myint=1) and/or ENV varables (export CFG_MYINT=1).
- **Layered Configuration:** Merges configuration data with a clear priority: ENV > CLI > JSON > TOML > Payload > Defaults
- **Immutability**: Configuration data is readonly (default) after loading.
- **Self-Documenting:** Generate help text from your configuration-schema definition.

---

## Quick Start

Define your configuration schema/model by inheriting from `ConfigModel`.
This will handle pydantic's parsing and validation while loading data from different sources. In this first example from the source payload:

```python
from typedconf import ConfigModel

# define configuration schema
class AppConfig(ConfigModel):
    app_name: str # required field, no default
    port: int = 8080 # default value

# load configuration
conf = AppConfig.load(payload={'app_name':'app'})

print(f"Running {conf.app_name} on port {conf.port}")   # Running app on port 8080
```

### Load configuration from TOML (or JSON)

Loading configuration data from source isn't a big deal. Most the time you will load data from configurations files. Let's say from this toml-file:

```toml
# config.toml v1
app_name = "myapp"
port = 2000
```

```python
from typedconf import ConfigModel

# define configuration schema
class AppConfig(ConfigModel):
    app_name: str
    port: int = 8080

# load configuration
conf = AppConfig.load(toml_files=['config.toml'])

print(f"Running {conf.app_name} on port {conf.port}")   # Running myapp on port 2000
```

### Data Validation and nested configuration

`ConfigModel` is just a pydantic `BaseModel`. So you can use the `Field` definitions to add descriptions, constraints, or default values.
Nested configuration can be applied by nesting `ConfigModel`classes.

```python
from pydantic import Field
from typedconf import ConfigModel, ConfigError

# define configuration schema
class DatabaseConfig(ConfigModel):
    con: str = Field(..., description="DB connection-string, required field.")
    user: str = Field(..., description="DB username, required field.")
    pwd: str = Field(..., description="DB password, required field.")

class AppConfig(ConfigModel):
    app_name: str = Field(..., description="application name, required field.")
    port: int = Field(8080, gt=1000, lt=9999, description="application listen on port. Between 1000 and 9999, defaullt=8080")
    db: DatabaseConfig = Field(default_factory=DatabaseConfig, description="database configuration")

# Load configuration
try:
    conf = AppConfig.load(toml_files=['config.toml'])
    print(f"Running {conf.app_name} on port {conf.port}. DB connected {conf.db.user} @ {conf.db.con}")
except ConfigError as e:
    print(e)
```

Loading from our "old" TOML-file will raise a `ConfigError`, because the stored data didn't reflect the new configuration-schema:

```text
3 validation errors for DatabaseConfig 
con Field required [type=missing, input_value={}, input_type=dict] For further information visit https://errors.pydantic.dev/2.11/v/missing
user Field required [type=missing, input_value={}, input_type=dict] For further information visit https://errors.pydantic.dev/2.11/v/missing
pwd Field required [type=missing, input_value={}, input_type=dict] For further information visit https://errors.pydantic.dev/2.11/v/missing
```

TOML is perfect for nested configurations using `tables` and JSON requires nested objects to reflect the same structure 🌞.
However, it's not the best idea to store sensitive or volatile data in a configuration-file. It is way better to [handle this kind of data by cli-interface and/or through environment variables](https://12factor.net/config).
Let's fix our TOML-file, while keeping the database password secret:

```toml
# config.toml v2
app_name = "toml-app"
port = 9090

[db]
con = "postgresql://localhost:5432/mydb"
user = "db_user_readonly"
```

**Just remember: don't store any sensitive data in configuration-files!**

### ENV & CLI Interface

Cool, now we can inject the missing (or secret) data through the cli- and env-interface. Both interfaces are enabled per default.

```sh
# cli-interface
$ python app.py --cfg_db__pwd="secret"
Running toml-app on port 9090. DB connected db_user_readonly @ postgresql://localhost:5432/mydb

# env-interface
$ export CFG_DB__PWD="secret"
$ python app.py
Running toml-app on port 9090. DB connected db_user_readonly @ postgresql://localhost:5432/mydb

# mix them
$ export CFG_DB__USER="db_user_admin"
$ export CFG_DB__PWD="secret"
$ CFG_PORT=2525 python app.py --cfg_app_name="cli-app"
Running cli-app on port 2525. DB connected db_user_admin @ postgresql://localhost:5432/mydb
```

The CLI- and ENV interface follows this convention:

- Case-sensitive: cli is *lowercase*, env is *UPPERCASE*
- CLI uses only long format for the arguments like `--key=val`
- Prefix: CLI arguments and ENV variables uses a prefix to avoid cross-situations in the shell. Defaults to `cfg_`. The prefix can be changed.
- Nested configuration will be seperated by `__` (two underscrores)
- Examples:
  - cli-interface: `--cfg_app_name` or `--cfg_db__user`
  - env-inteface: `CFG_APP_NAME` or `CFG_DB__USER`

### Priority Chain

TypedConf merges all data sources in a specific order. Higher-priority sources overwrite lower-priority ones:

1. **Environment Variables (Highest):** Overrides all other sources - i.e. `export CFG_DB__PWD="abc"`
2. **CLI Arguments:** Passed via command-line - i.e. `--cfg_db__pwd='abc'`
3. **JSON Files:** Merged from the provided list in the order specified
4. **TOML Files:** Merged from the provided list in the order specified
5. **Payload:** A dictionary passed directly to the load method - i.e. `.load(payload={"db":{"pwd":"abc"}})`
6. **Defaults (Lowest):** Default values defined in the `ConfigModel` class

*Note: The system performs a deep merge, preserving nested structures when partial overrides are provided.*

## Helpful Utilities

### Exporting Configurations

Export your current configuration instance to JSON or TOML format.

```python
# Export TOML string
print(conf.dumps_toml())

# Export JSON string
print(conf.dumps_json())
```

*Note: Exporting to TOML requires python package `tomli-w`.*

### CLI Help included

TypedConf can include a `--help` argument to your application and generates a nice helptext for all field-names based on their types and descriptions. Let's step back to our *nested configuration example* and add some help for the user:

```python
from pydantic import Field
from typedconf import ConfigModel, ConfigError

# define configuration schema
class DatabaseConfig(ConfigModel):
    con: str = Field(..., description="DB connection-string, required field.")
    user: str = Field(..., description="DB username, required field.")
    pwd: str = Field(..., description="DB password, required field.")

class AppConfig(ConfigModel):
    app_name: str = Field(..., description="application name, required field.")
    port: int = Field(8080, gt=1000, lt=9999, description="application listen on port. Between 1000 and 9999, defaullt=8080")
    db: DatabaseConfig = Field(default_factory=DatabaseConfig, description="database configuration")

# need some help?
if AppConfig.user_needs_help():
    print(f"MYAPP\n\nAvailable CLI Parameter\n{AppConfig.get_cli_helptext()}")
    exit(0)

# Load configuration
try:
    conf = AppConfig.load(toml_files=['config.toml'])
    print(f"Running {conf.app_name} on port {conf.port}. DB connected {conf.db.user} @ {conf.db.con}")
except ConfigError as e:
    print(e)
```

```text
$ python main.py --help
MYAPP

Available CLI Parameter
--cfg_app_name (AppConfig.app_name)
   type=str, default=None
   application name, required field.

--cfg_db__con (DatabaseConfig.con)
   type=str, default=None
   DB connection-string, required field.

--cfg_db__pwd (DatabaseConfig.pwd)
   type=str, default=None
   DB password, required field.

--cfg_db__user (DatabaseConfig.user)
   type=str, default=None
   DB username, required field.

--cfg_port (AppConfig.port)
   type=int, default=8080
   application listen on port. Between 1000 and 9999, defaullt=8080
```

AAAAAAAAAAAAAAAA

# TypedConf v2

A lightweight, type-safe configuration management library powered by [Pydantic](https://pydantic.dev/). Following the [12-factor application guide](https://12factor.net/config), it centralizes your application configuration by merging data from multiple sources with a clear priority: `ENV > CLI > JSON > TOML > Payload > Default`.

Heavily inspired by [dynaconf](https://www.dynaconf.com/), [pydantic](https://pydantic.dev/docs/validation/latest/get-started/), and [fastapi](https://fastapi.tiangolo.com/python-types/).

## Key Features

- **Type-Safe:** Built on Pydantic, ensuring configuration values are validated at runtime.
- **IDE Support:** Full type-hinting and IntelliSense support for seamless development.
- **Nested Support:** Easily handle complex configuration structures.
- **TOML and JSON Interface:** Load configuration from TOML and/or JSON files.
- **CLI and Environment Interface:** Seamlessly load data from CLI arguments (`--cfg_myint=1`) or ENV variables (`export CFG_MYINT=1`).
- **Layered Configuration:** Predictable merging priority.
- **Immutability:** Configuration data is read-only (by default) after loading.
- **Self-Documenting:** Generate help text directly from your schema definition.

---

## Quick Start

Define your configuration schema by inheriting from `ConfigModel`. This handles Pydantic's parsing and validation while loading data from various sources.

```python
from typedconf import ConfigModel

# Define configuration schema
class AppConfig(ConfigModel):
    app_name: str # Required field
    port: int = 8080 # Default value

# Load configuration from payload
conf = AppConfig.load(payload={'app_name': 'app'})

print(f"Running {conf.app_name} on port {conf.port}")
```

### Loading from TOML or JSON

You can load configuration data directly from files:

```toml
# config.toml
app_name = "myapp"
port = 2000
```

```python
from typedconf import ConfigModel

class AppConfig(ConfigModel):
    app_name: str
    port: int = 8080

# Load configuration
conf = AppConfig.load(toml_files=['config.toml'])

print(f"Running {conf.app_name} on port {conf.port}")
```

### Data Validation and Nested Configuration

`ConfigModel` is a Pydantic `BaseModel`. You can use `Field` definitions to add descriptions, constraints, or defaults. Nested configuration is supported by nesting `ConfigModel` classes.

```python
from pydantic import Field
from typedconf import ConfigModel, ConfigError

class DatabaseConfig(ConfigModel):
    con: str = Field(..., description="DB connection string, required.")
    user: str = Field(..., description="DB username, required.")
    pwd: str = Field(..., description="DB password, required.")

class AppConfig(ConfigModel):
    app_name: str = Field(..., description="Application name.")
    port: int = Field(8080, gt=1000, lt=9999, description="Port (1000-9999).")
    db: DatabaseConfig = Field(default_factory=DatabaseConfig, description="Database settings.")

# Load configuration
try:
    conf = AppConfig.load(toml_files=['config.toml'])
    print(f"Running {conf.app_name} on port {conf.port}. DB: {conf.db.user}")
except ConfigError as e:
    print(e)
```

**Note:** If the data in your TOML/JSON doesn't match the schema, `TypedConf` will raise a `ConfigError` with helpful validation details.

### ENV & CLI Interface

Both interfaces are enabled by default. They follow a specific convention:

- **Case-sensitivity:** CLI is lowercase, ENV is UPPERCASE.
- **Prefix:** Defaults to `cfg_` (can be customized).
- **Nesting:** Separated by `__` (double underscore).

```sh
# CLI usage
$ python app.py --cfg_db__pwd="secret"

# Environment variable usage
$ export CFG_DB__PWD="secret"
$ python app.py

# Mixed usage
$ export CFG_DB__USER="admin"
$ CFG_PORT=2525 python app.py --cfg_app_name="cli-app"
```

## Priority Chain

TypedConf merges data sources in the following order (highest priority overwrites lower):

1. **Environment Variables**
2. **CLI Arguments**
3. **JSON Files**
4. **TOML Files**
5. **Payload**
6. **Defaults** (Lowest)

## Helpful Utilities

### Exporting Configurations
Export your current configuration to JSON or TOML.

```python
# Export to string
print(conf.dumps_toml())
print(conf.dumps_json())
```
*Note: Exporting to TOML requires the `tomli-w` package.*

### CLI Help
TypedConf can generate a help menu for your application based on your schema's descriptions.

```python
if AppConfig.user_needs_help():
    print(f"MYAPP\n\nAvailable CLI Parameters\n{AppConfig.get_cli_helptext()}")
    exit(0)
```

This outputs:
```text
$ python main.py --help
MYAPP

Available CLI Parameters
--cfg_app_name (AppConfig.app_name)
   type=str, default=None
   Application name.
...
```
