param([string]$SteamVRRoot = 'D:\steam\steamapps\common\SteamVR')
$ErrorActionPreference = 'Stop'
$libraryPath = Join-Path ([IO.Path]::GetFullPath($SteamVRRoot)) 'bin\win64\openvr_api.dll'
if (-not (Test-Path -LiteralPath $libraryPath -PathType Leaf)) { throw 'SteamVR OpenVR library not found.' }
$escapedPath = $libraryPath.Replace('"', '""')
if (-not ('NilinRecovery.OpenVR' -as [type])) {
    Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
namespace NilinRecovery {
    public static class OpenVR {
        [DllImport(@"$escapedPath", CallingConvention=CallingConvention.Cdecl)]
        [return: MarshalAs(UnmanagedType.I1)]
        public static extern bool VR_IsHmdPresent();
        [DllImport(@"$escapedPath", CallingConvention=CallingConvention.Cdecl)]
        [return: MarshalAs(UnmanagedType.I1)]
        public static extern bool VR_IsRuntimeInstalled();
        [DllImport(@"$escapedPath", CallingConvention=CallingConvention.Cdecl)]
        public static extern uint VR_InitInternal2(out int error, int applicationType, System.IntPtr startupInfo);
        [DllImport(@"$escapedPath", CallingConvention=CallingConvention.Cdecl)]
        public static extern void VR_ShutdownInternal();
        [DllImport(@"$escapedPath", CallingConvention=CallingConvention.Cdecl)]
        public static extern System.IntPtr VR_GetVRInitErrorAsSymbol(int error);
    }
}
"@
}
$runtimeInstalled = [NilinRecovery.OpenVR]::VR_IsRuntimeInstalled()
$headsetPresent = [NilinRecovery.OpenVR]::VR_IsHmdPresent()
$initError = 0
try {
    # Background (3) never starts SteamVR or takes scene focus. The lightweight
    # HMD-present query alone can stay true while the streaming link is offline.
    $null = [NilinRecovery.OpenVR]::VR_InitInternal2([ref]$initError, 3, [IntPtr]::Zero)
    $errorSymbol = [Runtime.InteropServices.Marshal]::PtrToStringAnsi([NilinRecovery.OpenVR]::VR_GetVRInitErrorAsSymbol($initError))
    [pscustomobject]@{
        CheckedAt = [DateTimeOffset]::Now.ToString('o')
        RuntimeInstalled = $runtimeInstalled
        HeadsetPresent = $headsetPresent
        Ready = ($initError -eq 0)
        InitError = $initError
        ErrorSymbol = $errorSymbol
        SceneStarted = $false
    } | ConvertTo-Json
} finally {
    [NilinRecovery.OpenVR]::VR_ShutdownInternal()
}
