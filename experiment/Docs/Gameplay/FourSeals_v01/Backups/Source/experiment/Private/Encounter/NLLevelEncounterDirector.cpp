#include "Encounter/NLLevelEncounterDirector.h"

#include "AI/NLEnemyCharacter.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"

DEFINE_LOG_CATEGORY_STATIC(LogNLLevelEncounter, Log, All);

ANLLevelEncounterDirector::ANLLevelEncounterDirector()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = 0.1f;
}

void ANLLevelEncounterDirector::BeginPlay()
{
    Super::BeginPlay();
    RuntimeStages = Stages;
    StageStates.Init(ENLLevelStageState::Available, RuntimeStages.Num());
    bConfigurationValid = ValidateConfiguration(FailureReason);
    if (!bConfigurationValid)
    {
        UE_LOG(LogNLLevelEncounter, Error, TEXT("%s configuration rejected: %s"), *GetName(), *FailureReason.ToString());
    }
}

void ANLLevelEncounterDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    bEndingPlay = true;
    ReleasePlayerBinding();
    ReleaseEncounter();
    Super::EndPlay(EndPlayReason);
}

int32 ANLLevelEncounterDirector::FindStageIndex(FName StageId) const
{
    return RuntimeStages.IndexOfByPredicate([StageId](const FNLLevelEncounterStage& Stage) { return Stage.StageId == StageId; });
}

bool ANLLevelEncounterDirector::ValidateConfiguration(FName& OutReason) const
{
    OutReason = NAME_None;
    const auto Reject = [&OutReason](FName Reason) { OutReason = Reason; return false; };
    if (RuntimeStages.IsEmpty() || RuntimeStages.Num() > 128) return Reject(TEXT("InvalidStageCount"));
    TSet<FName> StageIds;
    TSet<FName> MasterIds;
    for (const FNLLevelEncounterStage& Stage : RuntimeStages)
    {
        if (Stage.StageId.IsNone() || StageIds.Contains(Stage.StageId)) return Reject(TEXT("InvalidOrDuplicateStageId"));
        StageIds.Add(Stage.StageId);
        if (Stage.TriggerCenter.ContainsNaN() || Stage.TriggerExtent.ContainsNaN()
            || Stage.TriggerExtent.GetMin() <= 0.0 || !FMath::IsFinite(Stage.WarningSeconds) || Stage.WarningSeconds < 0.0f)
            return Reject(TEXT("InvalidStageBoundsOrTiming"));
        if (Stage.EntryTransform.ContainsNaN() || !Stage.EntryTransform.GetRotation().IsNormalized()
            || Stage.EntryTransform.GetScale3D().GetMin() <= 0.0) return Reject(TEXT("InvalidStageEntryTransform"));
        if (Stage.Waves.IsEmpty() || Stage.SpawnPoints.IsEmpty()) return Reject(TEXT("MissingStageWavesOrPoints"));
        if (!Stage.MasterId.IsNone())
        {
            if (MasterIds.Contains(Stage.MasterId)) return Reject(TEXT("DuplicateMasterId"));
            MasterIds.Add(Stage.MasterId);
            for (const UNLWaveDefinition* Wave : Stage.Waves)
            {
                if (!IsValid(Wave)) return Reject(TEXT("MissingWaveDefinition"));
                for (const FNLWaveSpawnEntry& Entry : Wave->SpawnEntries)
                {
                    if (Entry.Count <= 0) return Reject(TEXT("InvalidMasterComposition"));
                }
            }
            const UNLWaveDefinition* FinalWave = Stage.Waves.Last();
            if (FinalWave->SpawnEntries.Num() != 1 || FinalWave->SpawnEntries[0].Count != 1)
                return Reject(TEXT("MasterFinalWaveMustPlanOneEnemy"));
        }
    }
    // Each dependency chain must terminate. Reject cycles and dangling references before any encounter can start.
    for (const FNLLevelEncounterStage& Stage : RuntimeStages)
    {
        TSet<FName> Visited;
        FName CurrentId = Stage.StageId;
        while (!CurrentId.IsNone())
        {
            if (Visited.Contains(CurrentId)) return Reject(TEXT("CyclicStageDependency"));
            Visited.Add(CurrentId);
            const int32 Index = FindStageIndex(CurrentId);
            if (!RuntimeStages.IsValidIndex(Index)) return Reject(TEXT("UnknownStageDependency"));
            CurrentId = RuntimeStages[Index].RequiredStageId;
        }
    }
    return true;
}

bool ANLLevelEncounterDirector::HasClearedDependency(int32 Index) const
{
    if (!RuntimeStages.IsValidIndex(Index)) return false;
    const FName Required = RuntimeStages[Index].RequiredStageId;
    if (Required.IsNone()) return true;
    const int32 RequiredIndex = FindStageIndex(Required);
    return StageStates.IsValidIndex(RequiredIndex) && StageStates[RequiredIndex] == ENLLevelStageState::Completed;
}

ENLLevelStageState ANLLevelEncounterDirector::GetStageStatus(FName StageId) const
{
    const int32 Index = FindStageIndex(StageId);
    if (!StageStates.IsValidIndex(Index)) return ENLLevelStageState::Unknown;
    if (!bConfigurationValid) return ENLLevelStageState::Locked;
    return StageStates[Index] == ENLLevelStageState::Available && !HasClearedDependency(Index)
        ? ENLLevelStageState::Locked : StageStates[Index];
}

ANLEncounterController* ANLLevelEncounterDirector::GetActiveEncounter() const
{
    return IsValid(ActiveEncounter) && !ActiveEncounter->IsActorBeingDestroyed() ? ActiveEncounter.Get() : nullptr;
}

FName ANLLevelEncounterDirector::GetActiveStageId() const
{
    return RuntimeStages.IsValidIndex(ActiveStageIndex) ? RuntimeStages[ActiveStageIndex].StageId : NAME_None;
}

FTransform ANLLevelEncounterDirector::GetRetryTransform() const
{
    return RuntimeStages.IsValidIndex(ActiveStageIndex) ? RuntimeStages[ActiveStageIndex].EntryTransform : FTransform::Identity;
}

int32 ANLLevelEncounterDirector::GetCompletedStageCount() const
{
    int32 Count = 0;
    for (const ENLLevelStageState State : StageStates) if (State == ENLLevelStageState::Completed) ++Count;
    return Count;
}

float ANLLevelEncounterDirector::GetWarningRemaining() const
{
    return GetWorld() && StageStates.IsValidIndex(ActiveStageIndex) && StageStates[ActiveStageIndex] == ENLLevelStageState::Warning
        ? static_cast<float>(FMath::Max(0.0, WarningEndsAt - GetWorld()->GetTimeSeconds())) : 0.0f;
}

bool ANLLevelEncounterDirector::IsBusy() const
{
    if (!StageStates.IsValidIndex(ActiveStageIndex)) return false;
    const ENLLevelStageState State = StageStates[ActiveStageIndex];
    return State == ENLLevelStageState::Warning || State == ENLLevelStageState::Active || State == ENLLevelStageState::Failed;
}

bool ANLLevelEncounterDirector::GetStageDefinition(FName StageId, FNLLevelEncounterStage& OutStage) const
{
    const int32 Index = FindStageIndex(StageId);
    if (!RuntimeStages.IsValidIndex(Index)) return false;
    OutStage = RuntimeStages[Index];
    return true;
}

bool ANLLevelEncounterDirector::IsStageInside(int32 Index, const FVector& Location) const
{
    if (!RuntimeStages.IsValidIndex(Index) || Location.ContainsNaN()) return false;
    const FNLLevelEncounterStage& Stage = RuntimeStages[Index];
    const FVector Delta = (Location - Stage.TriggerCenter).GetAbs();
    return Delta.X <= Stage.TriggerExtent.X && Delta.Y <= Stage.TriggerExtent.Y && Delta.Z <= Stage.TriggerExtent.Z;
}

bool ANLLevelEncounterDirector::IsLivingPlayer(const APawn* Pawn) const
{
    if (!IsValid(Pawn) || Pawn->IsActorBeingDestroyed() || Pawn->GetWorld() != GetWorld()) return false;
    const UNLCombatIdentityComponent* Identity = Pawn->FindComponentByClass<UNLCombatIdentityComponent>();
    const UNLCombatVitalsComponent* Vitals = Pawn->FindComponentByClass<UNLCombatVitalsComponent>();
    return Identity && Identity->GetFaction() == ENLCombatFaction::Player && Vitals
        && FMath::IsFinite(Vitals->GetHealth()) && Vitals->GetHealth() > 0.0f;
}

APawn* ANLLevelEncounterDirector::FindPlayerPawn() const
{
    if (!GetWorld()) return nullptr;
    for (FConstPlayerControllerIterator It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
    {
        const APlayerController* Controller = It->Get();
        APawn* Pawn = Controller ? Controller->GetPawn() : nullptr;
        if (IsLivingPlayer(Pawn)) return Pawn;
    }
    return nullptr;
}

bool ANLLevelEncounterDirector::TryActivateStage(FName StageId, APawn* TriggeringPawn)
{
    const int32 Index = FindStageIndex(StageId);
    if (!bConfigurationValid || bEndingPlay || bChangingEncounter || IsBusy() || !GetWorld() || GetWorld()->IsPaused()
        || GetStageStatus(StageId) != ENLLevelStageState::Available || !IsLivingPlayer(TriggeringPawn)
        || !IsStageInside(Index, TriggeringPawn->GetActorLocation())) return false;
    return BeginWarning(Index, TriggeringPawn);
}

bool ANLLevelEncounterDirector::BeginWarning(int32 Index, APawn* Pawn)
{
    if (!StageStates.IsValidIndex(Index) || !IsLivingPlayer(Pawn)) return false;
    ReleasePlayerBinding();
    ReleaseEncounter();
    ActiveStageIndex = Index;
    ActivePlayer = Pawn;
    ActiveVitals = Pawn->FindComponentByClass<UNLCombatVitalsComponent>();
    ActiveVitals->OnDied.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandlePlayerDied);
    FailureReason = NAME_None;
    WarningEndsAt = GetWorld()->GetTimeSeconds() + RuntimeStages[Index].WarningSeconds;
    SetStageState(Index, ENLLevelStageState::Warning);
    UE_LOG(LogNLLevelEncounter, Log, TEXT("%s stage %s warning %.2fs"), *GetName(), *GetActiveStageId().ToString(), RuntimeStages[Index].WarningSeconds);
    return true;
}

void ANLLevelEncounterDirector::StartActiveEncounter()
{
    if (!StageStates.IsValidIndex(ActiveStageIndex) || StageStates[ActiveStageIndex] != ENLLevelStageState::Warning || bChangingEncounter) return;
    if (!IsLivingPlayer(ActivePlayer.Get())) { FailActiveStage(TEXT("PlayerDied")); return; }
    const FNLLevelEncounterStage& Stage = RuntimeStages[ActiveStageIndex];
    const FTransform Transform = FTransform::Identity;
    ANLEncounterController* Encounter = GetWorld()->SpawnActorDeferred<ANLEncounterController>(ANLEncounterController::StaticClass(),
        Transform, this, ActivePlayer.Get(), ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Encounter) { FailActiveStage(TEXT("EncounterSpawnFailed")); return; }
    Encounter->Waves = Stage.Waves;
    Encounter->SpawnPoints = Stage.SpawnPoints;
    Encounter->Seed = Stage.Seed;
    Encounter->LevelId = LevelId;
    Encounter->EncounterId = Stage.StageId;
    Encounter->bEnableCheckpoints = false;
    Encounter->bShowReadyPreviews = false;
    ActiveEncounter = Encounter;
    Encounter->FinishSpawning(Transform);
    if (!IsValid(Encounter) || Encounter->IsActorBeingDestroyed()) { FailActiveStage(TEXT("EncounterSpawnFailed")); return; }
    Encounter->OnEncounterCompleted.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleEncounterCompleted);
    Encounter->OnEncounterFailed.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleEncounterFailed);
    Encounter->OnEnemyDefeated.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleEnemyDefeated);
    // BeginPlay validates the full wave plan before the event bindings above exist.
    if (Encounter->GetState() == ENLEncounterState::Failed) { FailActiveStage(Encounter->GetFailureReason()); return; }
    SetStageState(ActiveStageIndex, ENLLevelStageState::Active);
    if (StageStates[ActiveStageIndex] != ENLLevelStageState::Active || !IsLivingPlayer(ActivePlayer.Get())) return;
    Encounter->StartEncounter();
}

void ANLLevelEncounterDirector::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bConfigurationValid || bEndingPlay || bChangingEncounter || !GetWorld() || GetWorld()->IsPaused()) return;
    if (IsBusy())
    {
        const ENLLevelStageState State = StageStates[ActiveStageIndex];
        if (State == ENLLevelStageState::Failed) return;
        if (!IsLivingPlayer(ActivePlayer.Get())) { FailActiveStage(TEXT("PlayerDied")); return; }
        if (State == ENLLevelStageState::Warning)
        {
            if (GetWarningRemaining() <= 0.0f) StartActiveEncounter();
        }
        else if (!GetActiveEncounter()) FailActiveStage(TEXT("EncounterRemoved"));
        return;
    }
    APawn* Pawn = FindPlayerPawn();
    if (!Pawn) return;
    for (const FNLLevelEncounterStage& Stage : RuntimeStages)
    {
        if (TryActivateStage(Stage.StageId, Pawn)) break;
    }
}

void ANLLevelEncounterDirector::FailActiveStage(FName Reason)
{
    if (bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)) return;
    const ENLLevelStageState State = StageStates[ActiveStageIndex];
    if (State != ENLLevelStageState::Warning && State != ENLLevelStageState::Active) return;
    FailureReason = Reason.IsNone() ? FName(TEXT("EncounterFailed")) : Reason;
    WarningEndsAt = 0.0;
    SetStageState(ActiveStageIndex, ENLLevelStageState::Failed);
    if (ANLEncounterController* Encounter = GetActiveEncounter()) Encounter->FailEncounter(FailureReason);
    UE_LOG(LogNLLevelEncounter, Warning, TEXT("%s stage %s failed: %s"), *GetName(), *GetActiveStageId().ToString(), *FailureReason.ToString());
}

bool ANLLevelEncounterDirector::RetryActiveStage()
{
    if (!bConfigurationValid || bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Failed || !GetWorld() || GetWorld()->IsPaused()) return false;
    APawn* Pawn = IsLivingPlayer(ActivePlayer.Get()) ? ActivePlayer.Get() : FindPlayerPawn();
    if (!Pawn) return false;
    // Retry uses the original stage and seed. It never clears a dependency or emits a reward.
    return BeginWarning(ActiveStageIndex, Pawn);
}

void ANLLevelEncounterDirector::HandlePlayerDied()
{
    FailActiveStage(TEXT("PlayerDied"));
}

void ANLLevelEncounterDirector::HandleEncounterFailed(FName Reason)
{
    FailActiveStage(Reason);
}

void ANLLevelEncounterDirector::HandleEncounterCompleted()
{
    if (bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Active || !GetActiveEncounter()
        || ActiveEncounter->GetState() != ENLEncounterState::Completed) return;
    if (!IsLivingPlayer(ActivePlayer.Get())) { FailActiveStage(TEXT("PlayerDied")); return; }
    const int32 ClearedIndex = ActiveStageIndex;
    ReleasePlayerBinding();
    SetStageState(ClearedIndex, ENLLevelStageState::Completed);
    UE_LOG(LogNLLevelEncounter, Log, TEXT("%s cleared stage %s (%d/%d)"), *GetName(), *RuntimeStages[ClearedIndex].StageId.ToString(),
        GetCompletedStageCount(), GetStageCount());
}

void ANLLevelEncounterDirector::HandleEnemyDefeated(ANLEnemyCharacter* Enemy, FGuid EnemyRuntimeId, int32 SpawnOrdinal)
{
    if (bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Active || !IsLivingPlayer(ActivePlayer.Get())
        || !GetActiveEncounter() || !ActiveEncounter->OwnsEnemy(Enemy) || !IsValid(Enemy)
        || !Enemy->CombatIdentity || Enemy->CombatIdentity->GetRuntimeId() != EnemyRuntimeId) return;
    const FName MasterId = RuntimeStages[ActiveStageIndex].MasterId;
    if (MasterId.IsNone() || RewardedMasters.Contains(MasterId)
        || !IsFinalWaveFinalOrdinal(SpawnOrdinal, ActiveEncounter->GetPlannedCount(),
            ActiveEncounter->GetWaveIndex(), ActiveEncounter->GetWaveCount())) return;
    RewardedMasters.Add(MasterId);
    OnMasterDefeated.Broadcast(MasterId, Enemy->GetActorLocation());
}

bool ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(int32 SpawnOrdinal, int32 PlannedCount, int32 WaveIndex, int32 WaveCount)
{
    // Ordinals are assigned across the complete authored wave order by NLEncounterController.
    // Requiring both facts prevents an earlier disciple from consuming the master's first-kill reward.
    return PlannedCount > 0 && WaveCount > 0 && SpawnOrdinal == PlannedCount - 1 && WaveIndex == WaveCount - 1;
}

void ANLLevelEncounterDirector::ReleasePlayerBinding()
{
    if (UNLCombatVitalsComponent* Vitals = ActiveVitals.Get())
        Vitals->OnDied.RemoveDynamic(this, &ANLLevelEncounterDirector::HandlePlayerDied);
    ActiveVitals.Reset();
    ActivePlayer.Reset();
}

void ANLLevelEncounterDirector::ReleaseEncounter()
{
    TGuardValue<bool> Guard(bChangingEncounter, true);
    ANLEncounterController* Encounter = GetActiveEncounter();
    ActiveEncounter = nullptr;
    if (!Encounter) return;
    Encounter->OnEncounterCompleted.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleEncounterCompleted);
    Encounter->OnEncounterFailed.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleEncounterFailed);
    Encounter->OnEnemyDefeated.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleEnemyDefeated);
    Encounter->CancelEncounter();
    Encounter->Destroy();
}

void ANLLevelEncounterDirector::SetStageState(int32 Index, ENLLevelStageState State)
{
    if (!StageStates.IsValidIndex(Index) || StageStates[Index] == State) return;
    StageStates[Index] = State;
    if (!bEndingPlay) OnStageChanged.Broadcast(RuntimeStages[Index].StageId, State);
}
