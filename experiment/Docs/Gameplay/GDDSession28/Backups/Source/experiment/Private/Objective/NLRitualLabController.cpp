#include "Objective/NLRitualLabController.h"

#include "Objective/NLRitualObjective.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLTrainingEnemy.h"
#include "Combat/NLTrainingProjectileEmitter.h"
#include "Components/InputComponent.h"
#include "Engine/World.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"

ANLRitualLabController::ANLRitualLabController()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bTickEvenWhenPaused = false;
    PrimaryActorTick.TickGroup = TG_PostPhysics;
    InputPriority = 20;
}

void ANLRitualLabController::BeginPlay()
{
    Super::BeginPlay();
    if (IsValid(Objective))
    {
        Objective->OnCompletionPending.AddDynamic(this, &ANLRitualLabController::HandleCompletionPending);
        Objective->OnRescueCompleted.AddDynamic(this, &ANLRitualLabController::HandleCompleted);
        Objective->OnObjectiveFailed.AddDynamic(this, &ANLRitualLabController::HandleFailed);
    }
}

void ANLRitualLabController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    StopLaunchers();
    if (IsValid(Objective))
    {
        Objective->OnCompletionPending.RemoveDynamic(this, &ANLRitualLabController::HandleCompletionPending);
        Objective->OnRescueCompleted.RemoveDynamic(this, &ANLRitualLabController::HandleCompleted);
        Objective->OnObjectiveFailed.RemoveDynamic(this, &ANLRitualLabController::HandleFailed);
    }
    Super::EndPlay(EndPlayReason);
}

void ANLRitualLabController::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bReady)
    {
        APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
        if (!PC || !IsValid(Objective)) return;
        EnableInput(PC);
        if (InputComponent)
        {
            InputComponent->BindKey(EKeys::F5, IE_Pressed, this, &ANLRitualLabController::StartTrialInput);
            InputComponent->BindKey(EKeys::F6, IE_Pressed, this, &ANLRitualLabController::ResetTrial).bExecuteWhenPaused = true;
        }
        bReady = true;
        ResetTrial();
        if (bAutoStart) StartTrial();
    }
    if (!bTrialRunning || !IsValid(Objective)) return;
    // Track already flying hostile shots as explicit remaining threats. Reflection or
    // destruction removes them, so a last in-flight shot cannot follow an early success.
    for (TActorIterator<ANLCombatProjectile> It(GetWorld()); It; ++It)
    {
        const FName Id(*FString::Printf(TEXT("Lab.Projectile.%s.%d"),
            *It->GetAttackInstanceId().ToString(EGuidFormats::Digits), It->GetProjectileGeneration()));
        Objective->RegisterRemainingThreat(Id, *It);
    }
}

void ANLRitualLabController::StartTrialInput() { StartTrial(); }

bool ANLRitualLabController::StartTrial()
{
    if (bTrialRunning || !IsValid(Objective) || !GetWorld() || GetWorld()->IsPaused()) return false;
    ResetTrial();
    Objective->SetObjectiveActive(true);
    for (int32 I = 0; I < InterferenceActors.Num(); ++I)
        Objective->RegisterInterferenceSource(FName(*FString::Printf(TEXT("Lab.Caster.%02d"), I + 1)), InterferenceActors[I]);
    for (int32 I = 0; I < RequiredThreatActors.Num(); ++I)
        Objective->RegisterRemainingThreat(FName(*FString::Printf(TEXT("Lab.Threat.%02d"), I + 1)), RequiredThreatActors[I]);
    for (ANLTrainingProjectileEmitter* Launcher : Launchers)
    {
        if (!IsValid(Launcher)) continue;
        Launcher->TargetActor = Objective;
        Launcher->SetFiringEnabled(true);
    }
    bTrialRunning = true;
    TrialResult = TEXT("Running");
    return true;
}

void ANLRitualLabController::StopLaunchers()
{
    for (ANLTrainingProjectileEmitter* Launcher : Launchers)
        if (IsValid(Launcher)) Launcher->SetFiringEnabled(false);
}

void ANLRitualLabController::ResetTrial()
{
    if (!GetWorld() || !IsValid(Objective)) return;
    bTrialRunning = false;
    UGameplayStatics::SetGamePaused(this, false);
    StopLaunchers();
    ANLCombatProjectile::DestroyWorldProjectiles(GetWorld());
    TSet<AActor*> ResetActors;
    for (AActor* Actor : InterferenceActors) if (IsValid(Actor)) ResetActors.Add(Actor);
    for (AActor* Actor : RequiredThreatActors) if (IsValid(Actor)) ResetActors.Add(Actor);
    for (ANLTrainingProjectileEmitter* Actor : Launchers) if (IsValid(Actor)) ResetActors.Add(Actor);
    for (AActor* Actor : ResetActors)
    {
        if (ANLTrainingEnemy* Enemy = Cast<ANLTrainingEnemy>(Actor)) Enemy->ResetForEncounter();
        else if (ANLTrainingProjectileEmitter* Launcher = Cast<ANLTrainingProjectileEmitter>(Actor)) Launcher->ResetForEncounter();
        else if (UNLCombatVitalsComponent* SourceVitals = Actor->FindComponentByClass<UNLCombatVitalsComponent>()) SourceVitals->ResetVitals();
    }
    if (UNLCombatResolverSubsystem* Resolver = GetWorld()->GetSubsystem<UNLCombatResolverSubsystem>()) Resolver->ResetEncounterContacts();
    Objective->InitializeObjective(Objective->ObjectiveStableId, Objective->MaxIntegrity, LabRescueSeconds);
    Objective->SetObjectiveActive(false);
    TrialResult = TEXT("Ready");
}

void ANLRitualLabController::HandleCompletionPending(ANLRitualObjective* InObjective)
{
    if (InObjective != Objective) return;
    StopLaunchers();
    TrialResult = TEXT("ClearRemainingThreats");
}

void ANLRitualLabController::HandleCompleted(ANLRitualObjective* InObjective)
{
    if (InObjective != Objective) return;
    bTrialRunning = false;
    StopLaunchers();
    ANLCombatProjectile::DestroyWorldProjectiles(GetWorld());
    TrialResult = TEXT("Completed");
}

void ANLRitualLabController::HandleFailed(ANLRitualObjective* InObjective)
{
    if (InObjective != Objective) return;
    bTrialRunning = false;
    StopLaunchers();
    ANLCombatProjectile::DestroyWorldProjectiles(GetWorld());
    TrialResult = TEXT("Failed");
}

void ANLRitualLabHUD::DrawHUD()
{
    Super::DrawHUD();
    if (!Canvas || !GetWorld() || !GEngine) return;
    ANLRitualObjective* Ritual = nullptr;
    ANLRitualLabController* Trial = nullptr;
    for (TActorIterator<ANLRitualObjective> It(GetWorld()); It; ++It) { Ritual = *It; break; }
    for (TActorIterator<ANLRitualLabController> It(GetWorld()); It; ++It) { Trial = *It; break; }
    if (!Ritual || !Trial) return;
    UFont* Font = GEngine->GetMediumFont();
    DrawText(FString::Printf(TEXT("RITUAL OBJECTIVE LAB  |  %.0f-second accelerated exercise"), Trial->LabRescueSeconds), FLinearColor(.4f, .9f, 1.0f), 24.0f, 24.0f, Font, .9f);
    DrawText(FString::Printf(TEXT("INTEGRITY %.0f / %.0f     RESCUE %.1f%%"), Ritual->GetIntegrity(), Ritual->MaxIntegrity, Ritual->GetRescueProgress()),
        FLinearColor::White, 24.0f, 53.0f, Font, 1.0f);
    DrawText(FString::Printf(TEXT("Interference: %d     Remaining threats: %d     %s"),
        Ritual->GetInterferenceSourceCount(), Ritual->GetRemainingThreatCount(), *Trial->GetTrialResult().ToString()),
        FLinearColor(.95f, .8f, .4f), 24.0f, 83.0f, Font, .9f);
    DrawText(TEXT("F5 Begin | F6 Full retry | WASD Move | LMB Sword | RMB Guard | E Sword Qi | P Pause"),
        FLinearColor(.8f, .85f, .9f), 24.0f, Canvas->SizeY - 58.0f, Font, .75f);
    if (APawn* Pawn = GetOwningPawn())
    {
        if (const UNLCombatVitalsComponent* PlayerVitals = Pawn->FindComponentByClass<UNLCombatVitalsComponent>())
            DrawText(FString::Printf(TEXT("PLAYER HP %.0f    GUARD %.0f"), PlayerVitals->GetHealth(), PlayerVitals->GetGuard()),
                FLinearColor::White, 24.0f, Canvas->SizeY - 88.0f, Font, .8f);
    }
}
