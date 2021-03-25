param([string]$action,[string]$filepath)

$projectPath = $(pwd).Path
#Install this tool
if($action.ToLower() -eq "install"){
  git clone 'https://github.com/Chia-Network/clvm_tools.git' "$PSScriptRoot\clvm_tools"
  cd "$PSScriptRoot\clvm_tools"
  py -m venv venv
  & '.\venv\Scripts\activate'
  pip install -e .
  cd $projectPath
}
#Initialize a new project
if($action.ToLower() -eq "init"){
  mkdir "$projectPath\lib" | Out-Null
  Copy-Item -Path "$PSScriptRoot\std" -Destination "$projectPath\lib" -Recurse | Out-Null
  Copy-Item -Path "$PSScriptRoot\hello_world\*" -Destination $projectPath | Out-Null
  Write-Host "Run 'chialisp run helloworld.py' to test"
}
#Activate the venv
if(($action.ToLower() -eq "activate") -or ($action.ToLower() -eq "init")){
  . "$PSScriptRoot\clvm_tools\venv\Scripts\activate.ps1"
}
#Deactivate the venv
if($action.ToLower() -eq "deactivate"){
  deactivate
}
#Compile clvm
if(($action.ToLower() -eq "run") -or ($action.ToLower() -eq "build")){
  $clvmFiles = Get-ChildItem -Recurse $projectPath -Attributes !Directory
  if(($action.ToLower() -eq "build") -and ($filepath)) {
    $clvmFiles = $clvmFiles | ?{$_.Name -eq $filepath}
  } else {
    $clvmFiles = $clvmFiles | ?{$_.Name -Match '.*\.clvm$'}
  }
  $clvmFiles | %{
    $fileHash = (Get-FileHash $_.FullName).Hash
    $hexFileName = $_.FullName+'.'+$fileHash+'.hex'
    $fileRoot = $_.Name.Split('.')[0]
    $garbageFiles = Get-ChildItem -Recurse $projectPath -Attributes !Directory | ?{$_.Name -Match "$fileRoot\.clvm\.[0-9a-f]{64}\.hex$"} | ?{$_.Name -ne "$fileRoot.clvm.$fileHash.hex"} | Remove-Item
    if(!(Test-Path $hexFileName)){
      $buildPath = $PSScriptRoot+'\build.py'
      py $buildPath $_.FullName $fileHash
    }
  }
}
#Run python
if(($action.ToLower() -eq "run") -or ($action.ToLower() -eq "exec")){
  if($filepath){
    py $filepath
  } else {
    Write-Host 'No file path was specified to execute.'
  }
}
