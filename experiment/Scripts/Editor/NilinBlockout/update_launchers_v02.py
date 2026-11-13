from pathlib import Path
root=Path(r'D:\game design\experiment')
for kind in ('Demo','Editor'):
    p=root/f'Run_Blockout_{kind}.ps1'
    text=p.read_text(encoding='utf-8-sig')
    if not text.startswith('param('):text="param([ValidateSet('V06','V07')][string]$MapVersion = 'V07')\n"+text
    text=text.replace("$map = '/Game/ReversedScale/Maps/L_NilinBlockoutV06'","$map = '/Game/ReversedScale/Maps/L_NilinBlockout' + $MapVersion")
    text=text.replace("$mapFile = Join-Path $PSScriptRoot 'Content\\ReversedScale\\Maps\\L_NilinBlockoutV06.umap'","$mapFile = Join-Path $PSScriptRoot ('Content\\ReversedScale\\Maps\\L_NilinBlockout' + $MapVersion + '.umap')")
    p.write_text(text,encoding='utf-8-sig')
    (root/f'Run_Blockout_V06_{kind}.cmd').write_text(f'@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run_Blockout_{kind}.ps1" -MapVersion V06\n',encoding='ascii')
