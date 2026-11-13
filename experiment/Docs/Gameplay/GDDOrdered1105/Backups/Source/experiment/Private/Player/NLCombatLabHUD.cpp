#include "Player/NLCombatLabHUD.h"
#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"

#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLCombatRecoveryComponent.h"
#include "Combat/NLAbilityComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLTrainingEnemy.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Encounter/NLEncounterController.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Player/NLDesktopPlayerCharacter.h"
#include "Player/NLVRPlayerCharacter.h"

namespace
{
    FString GetEncounterFailureMessage(FName Reason)
    {
        if (Reason == TEXT("PlayerDefeated")) return TEXT("玩家已倒下");
        if (Reason == TEXT("NavigationFailed")) return TEXT("敌人无法到达玩家");
        if (Reason == TEXT("SpawnFailed")) return TEXT("出生位置暂不可用");
        if (Reason == TEXT("InvalidWaveConfig")) return TEXT("配置不可用");
        if (Reason == TEXT("EnemyRemoved")) return TEXT("敌人已离场，波次无法继续");
        return TEXT("波次无法继续，请重试");
    }
}

void ANLCombatLabHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || !PlayerOwner) return;
    const ANLDesktopPlayerCharacter* Player = Cast<ANLDesktopPlayerCharacter>(PlayerOwner->GetPawn());
    // Headsets use the OpenXR composition layer. With no tracked head, present
    // the exact same texture for desktop preview and screenshot verification.
    if (const ANLVRPlayerCharacter* VRPlayer = Cast<ANLVRPlayerCharacter>(Player))
    {
        if (!VRPlayer->HasValidHMDPose()) VRPlayer->DrawVRHUDPreview(Canvas);
        return;
    }
    if (!Player) return;
    const float W = Canvas->SizeX;
    const float H = Canvas->SizeY;
    const float X = W * 0.5f;
    const float Y = H * 0.5f;
    const float Now = GetWorld()->GetTimeSeconds();
    if (Player->Abilities)
    {
        DrawText(Player->Abilities->GetAbilityStatusText(), FLinearColor(.35f,.85f,.95f,1),
            42, H-178, GEngine->GetMediumFont(), 1.0f);
        if (Now-Player->Abilities->GetLastActivationTimeSeconds()<1.4)
        {
            const FNLAreaControlResult Result=Player->Abilities->GetLastAbilityResult();
            DrawText(FString::Printf(TEXT("%s · 清弹 %d · 震退 %d"),
                Result.Ability==ENLAreaAbility::Pulse?TEXT("震荡"):TEXT("逆鳞爆发"),Result.ProjectilesCleared,Result.EnemiesInterrupted),
                FLinearColor(.8f,.8f,.35f,1),X-120,Y+116,GEngine->GetMediumFont(),1.1f);
        }
    }
    if (const UNLCombatRecoveryComponent* Recovery = Player->CombatRecovery)
    {
        DrawText(FString::Printf(TEXT("化劲回元  %d / %d  ·  精准格挡积攒回血"),
            Recovery->GetRecoveryCharges(), Recovery->GetRequiredCharges()),
            FLinearColor(.35f,.85f,.65f,1.f),42,Canvas->SizeY-145,GEngine->GetMediumFont(),1.f);
        if (Recovery->GetLastRecoveredHealth()>0.f && Now-Recovery->GetLastRecoveryTimeSeconds()<1.2)
            DrawText(FString::Printf(TEXT("回元 +%.0f"),Recovery->GetLastRecoveredHealth()),
                FLinearColor(.35f,.85f,.65f,1.f),Canvas->SizeX*.5f-60,Canvas->SizeY*.62f,GEngine->GetMediumFont(),1.2f);
    }
    const FLinearColor Gold(0.82f, 0.72f, 0.46f, 1.0f);
    const FLinearColor Pale(0.90f, 0.92f, 0.88f, 1.0f);
    const FLinearColor Cyan(0.22f, 0.85f, 0.95f, 1.0f);
    const FLinearColor Red(0.95f, 0.30f, 0.24f, 1.0f);
    const FLinearColor Panel(0.015f, 0.025f, 0.028f, 0.80f);
    const ANLEncounterController* Encounter = Player->GetEncounterController();
    const bool bCheckpointLab = Player->AreCheckpointsEnabled();
    const bool bMixedLab = Encounter && Encounter->EncounterId == TEXT("Encounter.MixedDisciples");
    const bool bGuardCaptainLab = Encounter && Encounter->EncounterId == TEXT("Encounter.GuardCaptain");
    const bool bReflectionLab = Player->IsReflectionTrainingAvailable();
    const bool bSwordLab = Player->HasSwordEnemies();
    const bool bNeedsReflectionRetry = bReflectionLab && Player->GetPerfectParryCount() == 0 && !Player->HasLiveReflectionLauncher();
    int32 Total = 0;
    int32 Defeated = 0;
    int32 NavigationFailed = 0;
    if (Encounter)
    {
        Total = Encounter->GetPlannedCount();
        Defeated = Encounter->GetDefeatedCount();
    }
    else
    {
        for (TActorIterator<ANLTrainingEnemy> It(GetWorld()); It; ++It)
        {
            ++Total;
            if (It->Vitals->IsDead()) ++Defeated;
        }
        for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
        {
            ++Total;
            if (It->Vitals->IsDead()) ++Defeated;
            if (It->GetEnemyBrain()->GetState() == ENLEnemyState::Despawn && !It->Vitals->IsDead()) ++NavigationFailed;
        }
    }
    DrawRect(Panel,24,24,bCheckpointLab ? 540 : Encounter ? 480 : 426,
        bCheckpointLab ? 396 : Encounter ? 324 : bSwordLab ? 240 : 204);
    DrawText(bGuardCaptainLab ? TEXT("逆鳞  /  护阵执事") : bMixedLab ? TEXT("逆鳞  /  远近合击") : bCheckpointLab ? TEXT("逆鳞  /  检查点试炼") : Encounter ? TEXT("逆鳞  /  波次试炼") : TEXT("NILIN  /  COMBAT LAB"),
        Gold, 42, 36, GEngine->GetLargeFont(), 1.4f);
    const ENLEncounterState EncounterState = Encounter ? Encounter->GetState() : ENLEncounterState::Ready;
    const int32 WaveCount = Encounter ? Encounter->GetWaveCount() : 0;
    const bool bReadyEntry = EncounterState == ENLEncounterState::Ready || EncounterState == ENLEncounterState::Cancelled;
    const int32 WaveNumber = !Encounter ? 0 : bReadyEntry
        ? bCheckpointLab ? Encounter->GetEntryWaveIndex() + 1 : 0
        : FMath::Clamp(Encounter->GetWaveIndex() + 1, 0, WaveCount);
    const FString Progress = Encounter && bReadyEntry && Encounter->GetReadyPreviewCount() > 0
        ? FString::Printf(TEXT("波次 %d / %d   待战 %d   按 G 开始交战"),
            WaveNumber, WaveCount, Encounter->GetReadyPreviewCount())
        : Encounter
        ? FString::Printf(TEXT("波次 %d / %d   存活 %d   击败 %d / %d"),
            WaveNumber, WaveCount, Encounter->GetAliveCount(), Defeated, Total)
        : bReflectionLab
        ? FString::Printf(TEXT("Disciples: %d/%d   Reflection: %d/1"), Defeated, Total, FMath::Min(1,Player->GetPerfectParryCount()))
        : FString::Printf(TEXT("Disciples defeated: %d / %d"), Defeated, Total);
    DrawText(Progress, Pale, 42, 74, GEngine->GetMediumFont(), 1.4f);
    if (Encounter)
        DrawText(FString::Printf(TEXT("已生成 %d / %d   本波 %d / %d"), Encounter->GetSpawnedCount(), Total,
            Encounter->GetCurrentWaveSpawnedCount(), Encounter->GetCurrentWavePlannedCount()),
            Pale, 42, 106, GEngine->GetMediumFont(), 1.25f);
    auto DrawMeter = [&](const TCHAR* Label, float Value, float Maximum, float Top, FLinearColor Color)
    {
        DrawText(FString::Printf(TEXT("%s  %.0f / %.0f"), Label, Value, Maximum), Pale,
            42, Top, GEngine->GetMediumFont(), 1.35f);
        DrawRect(FLinearColor(0.07f,0.09f,0.11f,1), 42, Top + 25, 388, 8);
        DrawRect(Color, 42, Top + 25, 388 * FMath::Clamp(Value / FMath::Max(Maximum,1.0f),0.0f,1.0f), 8);
    };
    const float MeterOffset = Encounter ? 32.0f : 0.0f;
    DrawMeter(TEXT("HEALTH"), Player->Vitals->GetHealth(), Player->Vitals->GetMaxHealth(), 106 + MeterOffset, Red);
    DrawMeter(TEXT("GUARD"), Player->Guard->GetGuard(), Player->Guard->GetMaxGuard(), 151 + MeterOffset, Cyan);
    const bool bBroken = Player->Guard->IsGuardBroken();
    const bool bNeedsRelease = Player->Guard->IsWaitingForRelease();
    const FString GuardState = bBroken ? FString::Printf(TEXT("BROKEN  %.1fs  -  Release RMB"), Player->Guard->GetBreakRemainingSeconds())
        : bNeedsRelease ? TEXT("RELEASE RMB to recover guard")
        : (bReflectionLab || bMixedLab) && Player->Guard->IsPerfectWindowActive()
            ? FString::Printf(TEXT("PRECISION WINDOW: %.2fs"),Player->Guard->GetPerfectWindowRemaining())
        : Player->Guard->IsGuardActive() ? TEXT("MIRROR RAISED") : bMixedLab
            ? TEXT("右键举镜格挡，松开后再按可反弹符弹") : TEXT("RMB: Hold mirror in front of incoming shots");
    DrawText(GuardState, (bBroken || bNeedsRelease) ? Red : Cyan, 42, 198 + MeterOffset, GEngine->GetSmallFont(), 1.4f);
    if (Encounter)
    {
        FString StateMessage;
        FString InputMessage = TEXT("G 取消波次    R 重试");
        FLinearColor StateColor = Gold;
        switch (EncounterState)
        {
        case ENLEncounterState::Ready:
            StateMessage = bCheckpointLab ? FString::Printf(TEXT("待开始：从第 %d 波继续"), WaveNumber)
                : FString::Printf(TEXT("待开始：共 %d 波敌人"), WaveCount);
            InputMessage = bCheckpointLab ? TEXT("G 开始本波    R 返回检查点") : TEXT("G 开始波次    R 重新准备");
            break;
        case ENLEncounterState::Spawning:
            StateMessage = FString::Printf(TEXT("第 %d 波：敌人正在入场"), WaveNumber);
            StateColor = Red;
            break;
        case ENLEncounterState::WaitingClear:
            StateMessage = FString::Printf(TEXT("第 %d 波：击败剩余敌人"), WaveNumber);
            StateColor = Red;
            break;
        case ENLEncounterState::Intermission:
            StateMessage = FString::Printf(TEXT("第 %d 波已清除，下一波 %.1f 秒后开始"),
                WaveNumber, Encounter->GetIntermissionRemaining());
            break;
        case ENLEncounterState::Completed:
            StateMessage = FString::Printf(TEXT("试炼完成：已清除全部 %d 波"), WaveCount);
            InputMessage = bCheckpointLab ? FString::Printf(TEXT("R 重试第 %d 波"), Player->GetCheckpointWaveNumber()) : TEXT("R 重试");
            break;
        case ENLEncounterState::Failed:
            StateMessage = TEXT("试炼失败：") + GetEncounterFailureMessage(Encounter->GetFailureReason());
            StateColor = Red;
            InputMessage = bCheckpointLab ? FString::Printf(TEXT("R 重试第 %d 波"), Player->GetCheckpointWaveNumber()) : TEXT("R 重试");
            break;
        case ENLEncounterState::Cancelled:
            StateMessage = bCheckpointLab ? FString::Printf(TEXT("波次已取消：第 %d 波检查点保留"), Player->GetCheckpointWaveNumber())
                : TEXT("波次已取消");
            InputMessage = bCheckpointLab ? TEXT("G 从检查点开始    R 返回检查点") : TEXT("G 重新开始波次    R 重新准备");
            break;
        }
        DrawText(StateMessage, StateColor, 42, 264, GEngine->GetMediumFont(), 1.25f);
        DrawText(InputMessage, Pale, 42, 300, GEngine->GetMediumFont(), 1.25f);
        if (bCheckpointLab)
        {
            DrawText(Player->GetCheckpointStatusMessage(), Player->HasCheckpointFailure() ? Red : Cyan,
                42, 336, GEngine->GetMediumFont(), 1.2f);
            if (Player->HasCheckpointFailure())
                DrawText(Player->GetCheckpointFailureMessage(), Red, 42, 370, GEngine->GetMediumFont(), 1.15f);
        }
    }
    else if (bSwordLab)
        DrawText(Player->IsSwordDuelEnabled() ? TEXT("SWORD DUEL: ON  -  G to stop") : TEXT("SWORD DUEL: OFF  -  G to start"),
            Player->IsSwordDuelEnabled() ? Red : Gold,42,232,GEngine->GetMediumFont(),1.35f);
    DrawRect(Panel, W - 420, 24, 396, bGuardCaptainLab ? 238 : bMixedLab ? 206 : Encounter || bReflectionLab ? 156 : 124);
    if (Encounter)
    {
        FString WaveGoal;
        if (EncounterState == ENLEncounterState::Ready || EncounterState == ENLEncounterState::Cancelled)
            WaveGoal = bCheckpointLab ? FString::Printf(TEXT("按 G 从第 %d 波继续"), WaveNumber)
                : FString::Printf(TEXT("按 G 开始，清除全部 %d 波敌人"), WaveCount);
        else if (EncounterState == ENLEncounterState::Completed)
            WaveGoal = bCheckpointLab ? FString::Printf(TEXT("试炼完成，R 重试第 %d 波"), Player->GetCheckpointWaveNumber())
                : FString::Printf(TEXT("已完成全部 %d 波，按 R 重试"), WaveCount);
        else if (EncounterState == ENLEncounterState::Failed)
            WaveGoal = bCheckpointLab ? FString::Printf(TEXT("按 R 返回第 %d 波入口"), Player->GetCheckpointWaveNumber())
                : TEXT("按 R 重试，重新准备波次");
        else if (EncounterState == ENLEncounterState::Intermission)
            WaveGoal = TEXT("准备迎接下一波敌人");
        else
            WaveGoal = FString::Printf(TEXT("击败第 %d 波的全部 %d 名敌人"),
                WaveNumber, Encounter->GetCurrentWavePlannedCount());
        DrawText(TEXT("本波目标"), Gold, W - 402, 38, GEngine->GetMediumFont(), 1.55f);
        DrawText(WaveGoal, Pale, W - 402, 76, GEngine->GetMediumFont(), 1.25f);
    }
    else
    {
        DrawText(bNeedsReflectionRetry ? TEXT("LAUNCHER DEFEATED") : Player->IsProjectileTrainingEnabled() ? TEXT("SHOT TRAINING: ON") : TEXT("SHOT TRAINING: OFF"),
            Player->IsProjectileTrainingEnabled() ? Red : Gold, W - 402, 38, GEngine->GetMediumFont(), 1.55f);
        DrawText(bNeedsReflectionRetry ? TEXT("R: Retry the reflection drill") : TEXT("F: Start / stop the marked launcher"),
            Pale,W-402,76,GEngine->GetMediumFont(),1.25f);
    }
    const float Cooldown = Player->GetBladeQiCooldownRemaining();
    const FString BladeQiMessage = Encounter
        ? Cooldown > 0 ? FString::Printf(TEXT("刀气冷却  %.2f 秒"), Cooldown) : TEXT("E  刀气已就绪")
        : Cooldown > 0 ? FString::Printf(TEXT("BLADE QI  %.2fs"), Cooldown) : TEXT("BLADE QI READY  -  E");
    DrawText(BladeQiMessage,
        Cyan, W - 402, 112, GEngine->GetMediumFont(), 1.35f);
    if (Encounter)
        DrawText(TEXT("按住右键举起铜镜，抵挡刀击"),Gold,W-402,148,GEngine->GetMediumFont(),1.2f);
    else if (bReflectionLab)
        DrawText(TEXT("Tap RMB as a shot reaches you to reflect"),Gold,W-402,148,GEngine->GetMediumFont(),1.2f);
    if (bMixedLab)
        DrawText(TEXT("符弹将到时，重新按下右键可反弹"),Cyan,W-402,184,GEngine->GetMediumFont(),1.15f);
    if (bGuardCaptainLab)
    {
        DrawText(TEXT("正面连击破防，或绕到侧后方"), Cyan, W-402,184,GEngine->GetMediumFont(),1.15f);
        DrawText(TEXT("破防后反击，蓄力重击时注意闪避"), Gold, W-402,216,GEngine->GetMediumFont(),1.15f);
    }
    DrawRect(Panel, 24, H - 108, W - 48, 84);
    DrawText(Encounter ? TEXT("WASD 移动    鼠标 转向    左键 挥刀 (10)    E 刀气 (15)    按住右键 铜镜")
        : TEXT("WASD Move    Mouse Look    LMB Slash (10)    E Blade Qi (15)    Hold RMB Mirror"),
        Pale, 42, H - 95, GEngine->GetMediumFont(), 1.4f);
    DrawText(bCheckpointLab ? TEXT("G 开始/取消波次    Esc / P 暂停    R 返回检查点    Alt+F4 退出")
        : Encounter ? TEXT("G 开始/取消波次    Esc / P 暂停    R 重试    Alt+F4 退出")
        : bSwordLab ? TEXT("G Sword Duel    F Shot Training    Esc / P Pause    R Restart    Alt+F4 Exit")
        : TEXT("F Shot Training    Esc / P Pause    R Restart    Alt+F4 Exit"),
        Gold, 42, H - 60, GEngine->GetMediumFont(), 1.4f);
    DrawLine(X-4,Y,X+4,Y,Pale,1);
    DrawLine(X,Y-4,X,Y+4,Pale,1);
    if (Now - Player->GetLastHitTimeSeconds() < 0.24f)
    {
        for (int32 I=0; I<4; ++I)
        {
            const float SX=(I&1)?1.0f:-1.0f;
            const float SY=(I&2)?1.0f:-1.0f;
            DrawLine(X+SX*9,Y+SY*9,X+SX*17,Y+SY*17,Gold,2);
        }
    }
    if (Now - Player->GetLastParryTimeSeconds() < 0.65f)
        DrawText(TEXT("PERFECT REFLECTION"), Gold, X-140,Y+58,GEngine->GetMediumFont(),1.7f);
    else if (Now - Player->GetLastBlockTimeSeconds() < 0.45f)
        DrawText(TEXT("BLOCKED"), Cyan, X-58, Y+58, GEngine->GetMediumFont(), 1.7f);
    if (Now - Player->GetLastDamageTimeSeconds() < 0.45f)
    {
        DrawRect(FLinearColor(0.8f,0.02f,0.01f,0.35f),0,0,14,H);
        DrawRect(FLinearColor(0.8f,0.02f,0.01f,0.35f),W-14,0,14,H);
        DrawText(TEXT("HIT"), Red, X-25, Y+95, GEngine->GetMediumFont(), 1.6f);
    }
    if (NavigationFailed > 0)
        DrawText(TEXT("NAVIGATION FAILED  -  R to reset encounter"), Red,
            X-245,160,GEngine->GetMediumFont(),1.35f);
    if (!Encounter && Total > 0 && Defeated == Total && !Player->Vitals->IsDead())
    {
        const bool bComplete = !bReflectionLab || Player->GetPerfectParryCount() > 0;
        DrawText(bNeedsReflectionRetry ? TEXT("PRESS R TO RETRY REFLECTION")
            : bComplete ? TEXT("COMBAT CLEAR  -  R to restart") : TEXT("DISCIPLES CLEAR  -  Reflect one shot"),
            Gold,X-222,192,GEngine->GetMediumFont(),1.5f);
    }
    if (Player->Vitals->IsDead())
    {
        DrawRect(FLinearColor(0.03f,0.005f,0.005f,0.65f),0,0,W,H);
        DrawText(Encounter ? TEXT("玩家已倒下") : TEXT("DEFEATED"), Red, X-144,Y-60,GEngine->GetLargeFont(),2.2f);
        const FString RetryMessage = bCheckpointLab ? FString::Printf(TEXT("R  重试第 %d 波"), Player->GetCheckpointWaveNumber())
            : Encounter ? TEXT("R  重试波次") : TEXT("R  Restart encounter");
        DrawText(RetryMessage,Pale,X-135,Y+8,GEngine->GetMediumFont(),1.6f);
    }
    if (UGameplayStatics::IsGamePaused(this))
    {
        DrawRect(FLinearColor(0.01f,0.02f,0.025f,0.65f),0,0,W,H);
        const bool bRestoreBlocked = bCheckpointLab && Player->IsRestoringCheckpoint();
        DrawText(bRestoreBlocked ? TEXT("检查点恢复失败") : Encounter ? TEXT("已暂停") : TEXT("PAUSED"),
            bRestoreBlocked ? Red : Gold,X-(bRestoreBlocked ? 220 : 115),Y-60,GEngine->GetLargeFont(),2.2f);
        DrawText(bRestoreBlocked ? TEXT("已暂停，按 R 再试") : bCheckpointLab ? TEXT("Esc / P 继续    R 返回检查点")
            : Encounter ? TEXT("Esc / P 继续    R 重试") : TEXT("Esc / P Resume    R Restart"),
            Pale,X-180,Y+8,GEngine->GetMediumFont(),1.5f);
        DrawText(bRestoreBlocked ? Player->GetCheckpointFailureMessage()
            : Encounter ? TEXT("继续后再次按住右键举起铜镜。") : TEXT("Press RMB again after resuming to raise the mirror."),
            bRestoreBlocked ? Red : Cyan,X-292,Y+50,GEngine->GetMediumFont(),1.25f);
    }
}
