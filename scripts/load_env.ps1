param([string]$EnvFile = ".env.local")

if (-not (Test-Path $EnvFile)) { throw "Env file não encontrado: $EnvFile" }

Get-Content $EnvFile | ForEach-Object {
  $line = $_.Trim()
  if ($line -eq "" -or $line.StartsWith("#")) { return }

  $name, $value = $line.Split("=", 2)
  if ([string]::IsNullOrWhiteSpace($name)) { return }

  $name = $name.Trim()
  $value = $value.Trim().Trim('"').Trim("'")
  Set-Item -Path "Env:$name" -Value $value
}

Write-Host "Variáveis carregadas de $EnvFile"
