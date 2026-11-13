#include "Player/NLLevelCombatPlayer.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLCombatRecoveryComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLBladeComponent.h"
#include "Encounter/NLLevelEncounterDirector.h"
#include "Encounter/NLEncounterController.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Progression/NLMasterRewardSubsystem.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/TargetPoint.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"

ANLLevelCombatCharacter::ANLLevelCombatCharacter()
{
    bMatchEncounterEyeHeight = false;
    StandingEyeHeight = 161.0f;
    GetCharacterMovement()->MaxWalkSpeed = 500.0f;
    GetCharacterMovement()->MaxStepHeight = 35.0f;
    GetCharacterMovement()->SetWalkableFloorAngle(50.0f);
    PlayerCamera->FieldOfView = 85.0f;
}

void ANLLevelCombatCharacter::BeginPlay()
{
    Super::BeginPlay();
    InitialSafeLocation = GetActorLocation();
}

ANLLevelEncounterDirector* ANLLevelCombatCharacter::GetLevelDirector() const
{
    for (TActorIterator<ANLLevelEncounterDirector> It(GetWorld()); It; ++It)
        if (!It->IsActorBeingDestroyed()) return *It;
    return nullptr;
}

ANLEncounterController* ANLLevelCombatCharacter::GetEncounterController() const
{
    const ANLLevelEncounterDirector* Director = GetLevelDirector();
    return Director ? Director->GetActiveEncounter() : nullptr;
}

void ANLLevelCombatCharacter::Tick(float DeltaSeconds)
{
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
        GetCharacterMovement()->MaxWalkSpeed = PC->IsInputKeyDown(EKeys::LeftShift) ? 1000.0f : 500.0f;
    Super::Tick(DeltaSeconds);
    if (!GetWorld()->IsPaused() && Vitals && !Vitals->IsDead() && GetActorLocation().Z < -3000.0f)
        Vitals->ApplyCombatDamage(Vitals->GetMaxHealth());
}

void ANLLevelCombatCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    // Level encounters start from their authored regions. Remove lab-only toggle inputs.
    Input->KeyBindings.RemoveAll([](const FInputKeyBinding& B){return B.Chord.Key==EKeys::G || B.Chord.Key==EKeys::F;});
    Input->BindKey(EKeys::Tab,IE_Pressed,this,&ANLLevelCombatCharacter::ReleaseCursor).bExecuteWhenPaused=true;
    Input->BindKey(EKeys::One,IE_Pressed,this,&ANLLevelCombatCharacter::VisitEntry);
    Input->BindKey(EKeys::Two,IE_Pressed,this,&ANLLevelCombatCharacter::VisitRanged);
    Input->BindKey(EKeys::Three,IE_Pressed,this,&ANLLevelCombatCharacter::VisitBridge);
    Input->BindKey(EKeys::Four,IE_Pressed,this,&ANLLevelCombatCharacter::VisitSummit);
}

void ANLLevelCombatCharacter::ResetLab()
{
    ANLLevelEncounterDirector* Director = GetLevelDirector();
    if (!Director) return;
    const FName Stage = Director->GetActiveStageId();
    const bool bTraversalRecovery=Stage.IsNone() || Director->GetStageStatus(Stage)==ENLLevelStageState::Completed;
    if (bTraversalRecovery && !Vitals->IsDead()) return;
    UGameplayStatics::SetGamePaused(this,false);
    if (ANLEncounterController* Encounter=Director->GetActiveEncounter())
        Encounter->FailEncounter(TEXT("PlayerRetry"));
    Director->FailActiveStage(TEXT("PlayerRetry"));
    Guard->ResetGuard();
    Blade->ResetBladeHistory();
    CombatRecovery->ResetRecovery();
    ResetWeaponPose();
    ANLCombatProjectile::DestroyWorldProjectiles(GetWorld());
    GetWorld()->GetSubsystem<UNLCombatResolverSubsystem>()->ResetEncounterContacts();
    Vitals->ResetVitals();
    GetCharacterMovement()->StopMovementImmediately();
    const FTransform Entry=Stage.IsNone()?FTransform(GetActorRotation(),InitialSafeLocation):Director->GetRetryTransform();
    SetActorLocationAndRotation(Entry.GetLocation(),Entry.GetRotation(),false,nullptr,ETeleportType::TeleportPhysics);
    if (GetController()) GetController()->SetControlRotation(Entry.Rotator());
    GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    if (!bTraversalRecovery) Director->RetryActiveStage();
}

void ANLLevelCombatCharacter::ReleaseCursor()
{
    if (APlayerController* PC=Cast<APlayerController>(GetController()))
    {
        bCursorReleased=!bCursorReleased;
        LowerMirror();
        PC->bShowMouseCursor=bCursorReleased;
        if (bCursorReleased) PC->SetInputMode(FInputModeGameAndUI());
        else PC->SetInputMode(FInputModeGameOnly());
    }
}

void ANLLevelCombatCharacter::VisitNode(int32 Index)
{
    // Inspection jumps cannot bypass an active fight or mark a stage cleared.
    const ANLLevelEncounterDirector* Director=GetLevelDirector();
    if (Director && Director->IsBusy()) return;
    const FName Tag(*FString::Printf(TEXT("NLBlockout.Node.%02d"),Index));
    for (TActorIterator<ATargetPoint> It(GetWorld());It;++It)
    {
        if (!It->ActorHasTag(Tag)) continue;
        FHitResult Floor;
        const FVector Target=It->GetActorLocation();
        FCollisionQueryParams Params(SCENE_QUERY_STAT(LevelInspectionJump),false,this);
        if (!GetWorld()->LineTraceSingleByChannel(Floor,Target+FVector(0,0,60),Target-FVector(0,0,100),ECC_Visibility,Params)) return;
        const FVector Location=Floor.ImpactPoint+FVector(0,0,GetCapsuleComponent()->GetScaledCapsuleHalfHeight()+3);
        SetActorLocation(Location,false,nullptr,ETeleportType::TeleportPhysics);
        GetCharacterMovement()->StopMovementImmediately();
        if (GetController()) GetController()->SetControlRotation(It->GetActorRotation());
        return;
    }
}
void ANLLevelCombatCharacter::VisitEntry(){VisitNode(1);}
void ANLLevelCombatCharacter::VisitRanged(){VisitNode(4);}
void ANLLevelCombatCharacter::VisitBridge(){VisitNode(6);}
void ANLLevelCombatCharacter::VisitSummit(){VisitNode(7);}

ANLLevelCombatGameMode::ANLLevelCombatGameMode()
{
    DefaultPawnClass=ANLLevelCombatCharacter::StaticClass();
    HUDClass=ANLLevelCombatHUD::StaticClass();
}

void ANLLevelCombatGameMode::StartPlay()
{
    Super::StartPlay();
    UNLRunStateSubsystem* Run=GetGameInstance()->GetSubsystem<UNLRunStateSubsystem>();
    if (Run && !Run->GetRunId().IsValid()) Run->BeginRun(FGuid::NewGuid());
    for (TActorIterator<ANLLevelEncounterDirector> It(GetWorld());It;++It)
        It->OnMasterDefeated.AddUniqueDynamic(this,&ANLLevelCombatGameMode::HandleMasterDefeated);
}

void ANLLevelCombatGameMode::HandleMasterDefeated(FName MasterId,FVector Location)
{
    GetWorld()->GetSubsystem<UNLMasterRewardSubsystem>()->SpawnFirstDefeatReward(
        MasterId,Location-FVector(0,0,40),UGameplayStatics::GetPlayerPawn(this,0));
}

void ANLLevelCombatHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || !PlayerOwner) return;
    const ANLLevelCombatCharacter* Player=Cast<ANLLevelCombatCharacter>(PlayerOwner->GetPawn());
    if (!Player || !Player->Vitals) return;
    const FLinearColor Pale(.91f,.93f,.87f,1),Gold(.86f,.74f,.44f,1),Green(.28f,.85f,.58f,1),Red(.86f,.24f,.20f,1),Panel(.015f,.025f,.028f,.78f);
    const float W=Canvas->SizeX,H=Canvas->SizeY;
    const float Health=Player->Vitals->GetHealth(),Maximum=FMath::Max(1.f,Player->Vitals->GetMaxHealth());
    PresentedHealth=PresentedHealth<0 ? Health : FMath::FInterpTo(PresentedHealth,Health,GetWorld()->GetDeltaSeconds(),5.f);
    DrawRect(Panel,24,24,426,190);
    DrawText(TEXT("逆鳞 · 山路试炼"),Gold,42,34,GEngine->GetLargeFont(),1.f);
    DrawRect(FLinearColor(.13f,.13f,.13f,1),42,85,350,16);
    const float ActualWidth=350*FMath::Clamp(Health/Maximum,0.f,1.f);
    const float PresentedWidth=350*FMath::Clamp(PresentedHealth/Maximum,0.f,1.f);
    DrawRect(Red,42,85,FMath::Min(ActualWidth,PresentedWidth),16);
    DrawRect(Health<PresentedHealth?Gold:Green,42+FMath::Min(ActualWidth,PresentedWidth),85,FMath::Abs(ActualWidth-PresentedWidth),16);
    DrawText(FString::Printf(TEXT("生命 %.0f / %.0f    护势 %.0f"),Health,Maximum,Player->Vitals->GetGuard()),Pale,42,111,GEngine->GetMediumFont(),1.f);
    const UNLCombatRecoveryComponent* Recovery=Player->CombatRecovery;
    const int32 Required=Recovery?Recovery->GetRequiredCharges():3,Charges=Recovery?Recovery->GetRecoveryCharges():0;
    DrawText(TEXT("化劲回元"),Gold,42,148,GEngine->GetMediumFont(),1.f);
    for(int32 I=0;I<Required;++I) DrawRect(I<Charges?Green:FLinearColor(.20f,.24f,.23f,1),160+I*38,153,26,12);
    DrawText(FString::Printf(TEXT("%d / %d"),Charges,Required),Pale,290,147,GEngine->GetMediumFont(),.9f);
    if(Recovery && Recovery->GetLastRecoveredHealth()>0.f && GetWorld()->GetTimeSeconds()-Recovery->GetLastRecoveryTimeSeconds()<1.3f)
        DrawText(FString::Printf(TEXT("回元 +%.0f"),Recovery->GetLastRecoveredHealth()),Green,W*.5f-50,H*.62f,GEngine->GetMediumFont(),1.2f);
    else if(Player->GetLastParryTimeSeconds()>=0.f && GetWorld()->GetTimeSeconds()-Player->GetLastParryTimeSeconds()<.8f)
        DrawText(Health>=Maximum?TEXT("精准格挡 · 生命充盈"):TEXT("精准格挡 · 回元蓄积"),Gold,W*.5f-115,H*.62f,GEngine->GetMediumFont(),1.1f);
    const ANLLevelEncounterDirector* Director=Player->GetLevelDirector();
    if(Director)
    {
        const FName Id=Director->GetActiveStageId();
        FNLLevelEncounterStage Stage;
        const bool HasStage=Director->GetStageDefinition(Id,Stage);
        DrawRect(Panel,W-450,24,426,155);
        DrawText(FString::Printf(TEXT("遭遇进度 %d / %d"),Director->GetCompletedStageCount(),Director->GetStageCount()),Gold,W-430,36,GEngine->GetMediumFont(),1.f);
        DrawText(HasStage?Stage.DisplayName.ToString():TEXT("沿山路前进，进入区域后开始交战"),Pale,W-430,72,GEngine->GetMediumFont(),.95f);
        const ENLLevelStageState State=Director->GetStageStatus(Id);
        FString Status=TEXT("进入下一片区域继续");
        if(State==ENLLevelStageState::Warning) Status=FString::Printf(TEXT("敌人即将出现 %.1f 秒"),Director->GetWarningRemaining());
        else if(const ANLEncounterController* Encounter=Director->GetActiveEncounter())
            Status=FString::Printf(TEXT("波次 %d/%d  存活 %d  已击败 %d/%d"),Encounter->GetWaveIndex()+1,Encounter->GetWaveCount(),Encounter->GetAliveCount(),Encounter->GetDefeatedCount(),Encounter->GetPlannedCount());
        if(State==ENLLevelStageState::Completed) Status=TEXT("区域已清除，可继续前进");
        if(State==ENLLevelStageState::Failed) Status=TEXT("交战中断，按 R 返回本段入口重试");
        DrawText(Status,Pale,W-430,111,GEngine->GetMediumFont(),.9f);
    }
    DrawRect(Panel,24,H-83,W-48,60);
    DrawText(TEXT("WASD 移动  Shift 加速  左键挥剑  右键精准格挡  E 剑气  R 本段重试  P 暂停  Tab 鼠标"),Pale,40,H-70,GEngine->GetMediumFont(),.9f);
    DrawText(TEXT("3 次精准格挡回复 10 生命；宗师首杀掉落回复灵气，受伤时靠近领取。"),Gold,40,H-45,GEngine->GetMediumFont(),.85f);
    DrawLine(W*.5f-4,H*.5f,W*.5f+4,H*.5f,Pale,1);
    DrawLine(W*.5f,H*.5f-4,W*.5f,H*.5f+4,Pale,1);
    if(Player->Vitals->IsDead()) DrawText(TEXT("已倒下 · 按 R 重试本段"),Red,W*.5f-160,H*.5f+35,GEngine->GetLargeFont(),1.f);
}
