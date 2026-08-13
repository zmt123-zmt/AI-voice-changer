# ============================================================
# fix_fairseq_py311.ps1
# 修复 fairseq 0.12.2 + hydra 1.0.7 在 Python 3.11 下的兼容问题
# (dataclass mutable default -> field(default_factory=...))
#
# 用法:  在项目根目录执行
#   powershell -ExecutionPolicy Bypass -File tools\fix_fairseq_py311.ps1
#
# 说明:  幂等脚本, 可重复执行。
#        重装 rvc-python / fairseq / hydra-core 后需重新运行本脚本。
# ============================================================

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SitePackages = Join-Path $ProjectRoot ".venv\Lib\site-packages"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $SitePackages)) {
    Write-Host "ERROR: site-packages not found: $SitePackages" -ForegroundColor Red
    exit 1
}

function Patch-File {
    param([string]$Path, [string]$Old, [string]$New, [string]$Desc, [string]$Already = "")
    if (-not (Test-Path $Path)) {
        Write-Host "SKIP: $Path not found" -ForegroundColor Yellow
        return
    }
    $content = [System.IO.File]::ReadAllText($Path)
    if ($content.Contains($New) -or ($Already -ne "" -and $content.Contains($Already))) {
        Write-Host "OK (already patched): $Desc" -ForegroundColor DarkGray
        return
    }
    if (-not $content.Contains($Old)) {
        Write-Host "WARN: pattern not found in: $Desc" -ForegroundColor Yellow
        return
    }
    $content = $content.Replace($Old, $New)
    [System.IO.File]::WriteAllText($Path, $content)
    Write-Host "PATCHED: $Desc" -ForegroundColor Green
}

$fsCfg    = Join-Path $SitePackages "fairseq\dataclass\configs.py"
$fsInit   = Join-Path $SitePackages "fairseq\dataclass\initialize.py"
$fsTrans  = Join-Path $SitePackages "fairseq\models\transformer\transformer_config.py"
$hydraCfg = Join-Path $SitePackages "hydra\conf\__init__.py"

Write-Host "== 1) fairseq/dataclass/configs.py =="
$cfgPairs = @(
    @("common: CommonConfig = CommonConfig()", "common: CommonConfig = field(default_factory=CommonConfig)"),
    @("common_eval: CommonEvalConfig = CommonEvalConfig()", "common_eval: CommonEvalConfig = field(default_factory=CommonEvalConfig)"),
    @("distributed_training: DistributedTrainingConfig = DistributedTrainingConfig()", "distributed_training: DistributedTrainingConfig = field(default_factory=DistributedTrainingConfig)"),
    @("dataset: DatasetConfig = DatasetConfig()", "dataset: DatasetConfig = field(default_factory=DatasetConfig)"),
    @("optimization: OptimizationConfig = OptimizationConfig()", "optimization: OptimizationConfig = field(default_factory=OptimizationConfig)"),
    @("checkpoint: CheckpointConfig = CheckpointConfig()", "checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)"),
    @("bmuf: FairseqBMUFConfig = FairseqBMUFConfig()", "bmuf: FairseqBMUFConfig = field(default_factory=FairseqBMUFConfig)"),
    @("generation: GenerationConfig = GenerationConfig()", "generation: GenerationConfig = field(default_factory=GenerationConfig)"),
    @("eval_lm: EvalLMConfig = EvalLMConfig()", "eval_lm: EvalLMConfig = field(default_factory=EvalLMConfig)"),
    @("interactive: InteractiveConfig = InteractiveConfig()", "interactive: InteractiveConfig = field(default_factory=InteractiveConfig)"),
    @("ema: EMAConfig = EMAConfig()", "ema: EMAConfig = field(default_factory=EMAConfig)")
)
foreach ($p in $cfgPairs) { Patch-File $fsCfg $p[0] $p[1] "configs.py: $($p[0])" }

Write-Host "== 2) fairseq/dataclass/initialize.py =="
Patch-File $fsInit "import logging`nfrom hydra.core.config_store import ConfigStore" `
    "import logging`nimport dataclasses`nfrom hydra.core.config_store import ConfigStore" `
    "initialize.py: import dataclasses"
Patch-File $fsInit "        v = FairseqConfig.__dataclass_fields__[k].default" `
    "        f = FairseqConfig.__dataclass_fields__[k]`n        # Python 3.11: default_factory fields have default == dataclasses.MISSING`n        v = f.default_factory() if f.default is dataclasses.MISSING else f.default" `
    "initialize.py: hydra_init supports default_factory" `
    "f.default_factory() if f.default is dataclasses.MISSING"

Write-Host "== 3) fairseq/models/transformer/transformer_config.py =="
Patch-File $fsTrans "encoder: EncDecBaseConfig = EncDecBaseConfig()" "encoder: EncDecBaseConfig = field(default_factory=EncDecBaseConfig)" "transformer_config.py: encoder"
Patch-File $fsTrans "decoder: DecoderConfig = DecoderConfig()" "decoder: DecoderConfig = field(default_factory=DecoderConfig)" "transformer_config.py: decoder"
Patch-File $fsTrans "quant_noise: QuantNoiseConfig = field(default=QuantNoiseConfig())" "quant_noise: QuantNoiseConfig = field(default_factory=QuantNoiseConfig)" "transformer_config.py: quant_noise"

Write-Host "== 4) hydra/conf/__init__.py =="
$hydraPairs = @(
    @("override_dirname: OverrideDirname = OverrideDirname()", "override_dirname: OverrideDirname = field(default_factory=OverrideDirname)"),
    @("config: JobConfig = JobConfig()", "config: JobConfig = field(default_factory=JobConfig)"),
    @("run: RunDir = RunDir()", "run: RunDir = field(default_factory=RunDir)"),
    @("sweep: SweepDir = SweepDir()", "sweep: SweepDir = field(default_factory=SweepDir)"),
    @("help: HelpConf = HelpConf()", "help: HelpConf = field(default_factory=HelpConf)"),
    @("hydra_help: HydraHelpConf = HydraHelpConf()", "hydra_help: HydraHelpConf = field(default_factory=HydraHelpConf)"),
    @("overrides: OverridesConf = OverridesConf()", "overrides: OverridesConf = field(default_factory=OverridesConf)"),
    @("job: JobConf = JobConf()", "job: JobConf = field(default_factory=JobConf)"),
    @("runtime: RuntimeConf = RuntimeConf()", "runtime: RuntimeConf = field(default_factory=RuntimeConf)")
)
foreach ($p in $hydraPairs) { Patch-File $hydraCfg $p[0] $p[1] "hydra conf/__init__.py: $($p[0])" }

Write-Host ""
Write-Host "== 5) Verify imports =="
& $PythonExe -c "import fairseq, hydra; print('fairseq + hydra import OK')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "VERIFY FAILED - check errors above" -ForegroundColor Red
    exit 1
}
Write-Host "All patches applied. Done." -ForegroundColor Green
