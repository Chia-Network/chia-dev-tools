$ErrorActionPreference = "Stop"

$script_directory = Split-Path $MyInvocation.MyCommand.Path -Parent
$command = $args[0]
$parameters = [System.Collections.ArrayList]$args
$parameters.RemoveAt(0)

if (Test-Path -Path $script_directory/venv) {
    & $script_directory/venv/Scripts/Activate.ps1
}
& $command @parameters

exit $LASTEXITCODE
