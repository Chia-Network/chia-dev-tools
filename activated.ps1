$ErrorActionPreference = "Stop"

$script_directory = Split-Path $MyInvocation.MyCommand.Path -Parent
if (Test-Path -Path $script_directory/venv) {
    & $script_directory/venv/Scripts/Activate.ps1
   }
& @args

exit $LASTEXITCODE
