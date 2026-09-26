<#
.SYNOPSIS
  Train aster-illustrious-v2 (SDXL LoRA) with kohya sd-scripts. PC only.

.DESCRIPTION
  Checks the dataset (every image captioned, every caption starting with asterfen),
  computes num_repeats from the image count, writes a resolved dataset config into the
  output folder, then runs sdxl_train_network.py with aster-v2.toml.

  Checkpoints land in -OutDir as aster-illustrious-v2-0000NN.safetensors (every 2 epochs)
  plus aster-illustrious-v2.safetensors (final). None is copied into ComfyUI: pick one with
  compare.py first. See ..\README.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File train.ps1 -DryRun
  powershell -ExecutionPolicy Bypass -File train.ps1
  powershell -ExecutionPolicy Bypass -File train.ps1 -LowVram -LowRam     # 12 GB card, 16 GB RAM
#>
param(
  [string]$SdScripts  = "$env:USERPROFILE\sd-scripts",
  [string]$Checkpoint = "$env:USERPROFILE\Documents\ComfyUI\models\checkpoints\furrytoonmix_xlIllustriousV2.safetensors",
  [string]$Dataset    = "$env:USERPROFILE\lora-v2\dataset",
  [string]$OutDir     = "$env:USERPROFILE\lora-v2\output",
  [string]$Python     = "",   # default: sd-scripts\venv\Scripts\python.exe, else python on PATH
  [int]$StepsPerEpoch = 180,
  [int]$SampleEvery   = 2,
  [switch]$NoSamples,   # skip sample renders during training (saves time and VRAM)
  [switch]$LowVram,     # --fp8_base: base model weights in fp8, about 3 GB less VRAM
  [switch]$LowRam,      # --lowram: load the model straight to the GPU instead of RAM
  [switch]$Fp16,        # fp16 instead of bf16, for cards older than RTX 30xx
  [switch]$DryRun       # check everything and print the command; train nothing
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Trigger = "asterfen"

function Fail($msg) { Write-Host "not ready: $msg" -ForegroundColor Red; exit 2 }

# ---- preflight --------------------------------------------------------------
$trainer = Join-Path $SdScripts "sdxl_train_network.py"
if (-not (Test-Path $trainer)) {
  Fail "no sd-scripts at $SdScripts. Install: git clone https://github.com/kohya-ss/sd-scripts $SdScripts, then follow its README (venv + requirements), or pass -SdScripts."
}
if (-not (Test-Path $Checkpoint)) { Fail "base checkpoint not found: $Checkpoint (pass -Checkpoint)" }
if (-not (Test-Path $Dataset))    { Fail "dataset folder not found: $Dataset (run curate.py build, then caption.py)" }

$images = @(Get-ChildItem -LiteralPath $Dataset -File | Where-Object { @(".png", ".jpg", ".jpeg", ".webp") -contains $_.Extension.ToLower() })
$n = $images.Count
if ($n -lt 15) { Fail "only $n images in $Dataset; the plan is 25-40" }

$problems = @()
foreach ($img in $images) {
  $txt = [IO.Path]::ChangeExtension($img.FullName, ".txt")
  if (-not (Test-Path -LiteralPath $txt)) { $problems += "$($img.Name): no caption"; continue }
  $cap = (Get-Content -LiteralPath $txt -Raw).Trim()
  if (-not $cap.StartsWith("$Trigger,")) { $problems += "$($img.Name): caption does not start with '$Trigger,'" }
  if ($cap -match "many arms|parallel work|two tails|multiple tails") { $problems += "$($img.Name): banned phrase in caption" }
}
if ($problems.Count) { Fail ("captions:`n  " + ($problems -join "`n  ") + "`nRun: python caption.py --dataset $Dataset") }

try {
  Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:8000/system_stats" | Out-Null
  Write-Warning "ComfyUI is running on :8000. It holds several GB of RAM and VRAM; close it before training on a 16 GB machine."
} catch { }

$freeGb = [Math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)
if ($freeGb -lt 10) { Write-Warning "only $freeGb GB RAM free. Loading SDXL peaks near 10 GB; close apps, or use -LowRam (see README)." }

# ---- resolved dataset config ------------------------------------------------
$repeats = [Math]::Max(1, [int][Math]::Round($StepsPerEpoch / $n))
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$template = Get-Content -LiteralPath (Join-Path $Here "dataset.toml") -Raw
$resolved = $template.Replace("__DATASET_DIR__", (Resolve-Path -LiteralPath $Dataset).Path) -replace "num_repeats = \d+", "num_repeats = $repeats"
$dsPath = Join-Path $OutDir "dataset.resolved.toml"
[IO.File]::WriteAllText($dsPath, $resolved, (New-Object System.Text.UTF8Encoding $false))  # no BOM: the toml parser rejects it

$epochs = 12
$steps = $n * $repeats * $epochs
Write-Host "$n images x $repeats repeats x $epochs epochs = $steps steps (batch 1)"

# ---- command ----------------------------------------------------------------
$py = if ($Python) { $Python } else { Join-Path $SdScripts "venv\Scripts\python.exe" }
if (-not (Test-Path $py)) { Write-Warning "no $py; using python on PATH"; $py = "python" }
$cmd = @(
  "-m", "accelerate.commands.launch", "--num_processes", "1", "--num_machines", "1",
  "--num_cpu_threads_per_process", "1", "--dynamo_backend", "no",
  $trainer,
  "--config_file", (Join-Path $Here "aster-v2.toml"),
  "--dataset_config", $dsPath,
  "--pretrained_model_name_or_path", $Checkpoint,
  "--output_dir", $OutDir,
  "--logging_dir", (Join-Path $OutDir "logs")
)
if ($Fp16)    { $cmd += @("--mixed_precision", "fp16") }
if ($LowVram) { $cmd += "--fp8_base" }
if ($LowRam)  { $cmd += "--lowram" }
if (-not $NoSamples) {
  $cmd += @("--sample_prompts", (Join-Path $Here "sample_prompts.txt"), "--sample_every_n_epochs", "$SampleEvery")
}

Write-Host "`n$py $($cmd -join ' ')`n"
if ($DryRun) { Write-Host "dry run: nothing trained."; exit 0 }

Push-Location $SdScripts
try { & $py @cmd; $code = $LASTEXITCODE } finally { Pop-Location }
if ($code -ne 0) { Write-Host "training failed (exit $code)" -ForegroundColor Red; exit $code }
Write-Host "`nDone. Checkpoints in $OutDir. Next: copy them into ComfyUI\models\loras and run compare.py (README step 6)."
