$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$gripDir='D:\game design\experiment\Docs\Gameplay\HandGripPolish1104'
$before=[Drawing.Image]::FromFile((Join-Path $gripDir 'BeforeMatched\D_cut_side.png'))
$after=[Drawing.Image]::FromFile((Join-Path $gripDir 'After\D_cut_side.png'))
$canvas=[Drawing.Bitmap]::new(2000,1080)
$graphics=[Drawing.Graphics]::FromImage($canvas)
$font=[Drawing.Font]::new('Microsoft YaHei',28,[Drawing.FontStyle]::Bold)
try {
    $graphics.Clear([Drawing.Color]::FromArgb(20,25,31))
    $graphics.DrawImage($before,[Drawing.Rectangle]::new(0,80,1000,1000))
    $graphics.DrawImage($after,[Drawing.Rectangle]::new(1000,80,1000,1000))
    $graphics.DrawString('BEFORE',[Drawing.Font]$font,[Drawing.Brushes]::Salmon,[single]35,[single]18)
    $graphics.DrawString('AFTER  |  D ATTACK',[Drawing.Font]$font,[Drawing.Brushes]::LightGreen,[single]1035,[single]18)
    $canvas.Save((Join-Path $gripDir 'HandGrip_BeforeAfter.png'),[Drawing.Imaging.ImageFormat]::Png)
} finally {
    $font.Dispose();$graphics.Dispose();$canvas.Dispose();$before.Dispose();$after.Dispose()
}
