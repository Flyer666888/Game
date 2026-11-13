#include "Encounter/NLLevelEncounterDirector.h"

#include "AI/NLEnemyCharacter.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Encounter/NLEncounterController.h"
#include "Encounter/NLWaveDefinition.h"
#include "Objective/NLRitualObjective.h"
#include "Player/NLDesktopPlayerCharacter.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Progression/NLUpgradeDefinition.h"
#include "Progression/NLOrdinaryLootSubsystem.h"
#include "Engine/GameInstance.h"
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
    RuntimeUpgradeDefinition = UpgradeDefinition;
    StageStates.Init(ENLLevelStageState::Available, RuntimeStages.Num());
    bConfigurationValid = ValidateConfiguration(FailureReason);
    BoundRunState = ResolveRunState();
    if (bConfigurationValid && RuntimeUpgradeDefinition
        && (!BoundRunState || !BoundRunState->ConfigureUpgradeDefinition(RuntimeUpgradeDefinition)))
    {
        bConfigurationValid = false;
        FailureReason = TEXT("InvalidLevelUpgradeDefinition");
    }
    if (BoundRunState)
    {
        BoundRunState->OnRunStateChanged.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleRunStateChanged);
        HandleRunStateChanged();
    }
    if (!bConfigurationValid)
    {
        UE_LOG(LogNLLevelEncounter, Error, TEXT("%s configuration rejected: %s"), *GetName(), *FailureReason.ToString());
    }
}

void ANLLevelEncounterDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    bEndingPlay = true;
    if (BoundRunState)
    {
        BoundRunState->OnRunStateChanged.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleRunStateChanged);
        if (RuntimeUpgradeDefinition && BoundRunState->GetUpgradeDefinition() == RuntimeUpgradeDefinition)
            BoundRunState->ConfigureUpgradeDefinition(nullptr);
    }
    BoundRunState = nullptr;
    ReleasePlayerBinding();
    ReleaseObjective();
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
    TSet<FName> SealIds;
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
        if (Stage.ObjectiveStableId.ToString().Len() > 128) return Reject(TEXT("InvalidObjectiveStableId"));
        if (!FMath::IsFinite(Stage.ObjectiveProgressTarget) || Stage.ObjectiveProgressTarget <= 0.0f
            || Stage.ObjectiveProgressTarget > 100.0f
            || (Stage.ObjectiveStableId.IsNone() && (Stage.bContinueObjectiveFromPreviousStage || Stage.ObjectiveProgressTarget != 100.0f)))
            return Reject(TEXT("InvalidObjectiveProgressTarget"));
        // A rescue can stop its spawn plan early; it cannot also promise a final-master reward.
        if (!Stage.ObjectiveStableId.IsNone() && (!Stage.MasterId.IsNone() || !Stage.SealId.IsNone()))
            return Reject(TEXT("ObjectiveStageCannotGrantMasterSeal"));
        const int32 MaximumUpgradeLevel = RuntimeUpgradeDefinition && RuntimeUpgradeDefinition->bEnableSecondUpgrade ? 3 : 2;
        if (Stage.MinimumUpgradeLevelOnComplete < 1 || Stage.MinimumUpgradeLevelOnComplete > MaximumUpgradeLevel
            || (Stage.MinimumUpgradeLevelOnComplete > 1 && !RuntimeUpgradeDefinition))
            return Reject(TEXT("InvalidStageUpgradeGuarantee"));
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
        if (!Stage.SealId.IsNone())
        {
            if (UNLRunStateSubsystem::SealForMaster(Stage.MasterId) != Stage.SealId)
                return Reject(TEXT("MasterSealIdentityMismatch"));
            if (SealIds.Contains(Stage.SealId)) return Reject(TEXT("DuplicateSealProvider"));
            SealIds.Add(Stage.SealId);
        }
        TSet<FName> RequiredSeals;
        for (FName SealId : Stage.RequiredSealIds)
        {
            if (UNLRunStateSubsystem::MasterForSeal(SealId).IsNone() || RequiredSeals.Contains(SealId))
                return Reject(TEXT("InvalidRequiredSealIds"));
            RequiredSeals.Add(SealId);
        }
    }
    // Each dependency chain must terminate. Reject cycles and dangling references before any encounter can start.
    for (const FNLLevelEncounterStage& Stage : RuntimeStages)
    {
        if (Stage.bContinueObjectiveFromPreviousStage)
        {
            const int32 PreviousIndex = FindStageIndex(Stage.RequiredStageId);
            if (!RuntimeStages.IsValidIndex(PreviousIndex)) return Reject(TEXT("MissingObjectivePredecessor"));
            const FNLLevelEncounterStage& Previous = RuntimeStages[PreviousIndex];
            if (Stage.ObjectiveStableId.IsNone() || Previous.ObjectiveStableId != Stage.ObjectiveStableId
                || Previous.ObjectiveProgressTarget >= Stage.ObjectiveProgressTarget)
                return Reject(TEXT("InvalidObjectivePhaseSequence"));
        }
        for (FName SealId : Stage.RequiredSealIds)
            if (!SealIds.Contains(SealId)) return Reject(TEXT("MissingSealProvider"));
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

UNLRunStateSubsystem* ANLLevelEncounterDirector::ResolveRunState() const
{
    const UGameInstance* Instance = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
    return Instance ? Instance->GetSubsystem<UNLRunStateSubsystem>() : nullptr;
}

void ANLLevelEncounterDirector::HandleRunStateChanged()
{
    if (!BoundRunState || bEndingPlay || !bConfigurationValid) return;
    const FGuid RunId = BoundRunState->GetRunId();
    if (ObservedRunId.IsValid() && RunId != ObservedRunId)
    {
        ReleasePlayerBinding();
        ReleaseObjective();
        ReleaseEncounter();
        ActiveStageIndex = INDEX_NONE;
        EntryProgression = FNLProgressionState();
        EntryBurstEnergy = 0.0f;
        bHasEntryProgression = false;
        EntryObjective = FNLObjectiveSnapshot();
        CompletedObjectiveSnapshots.Reset();
        CompletedObjectiveOwners.Reset();
        bRetryProgressionPrepared = false;
        RewardedMasters.Reset();
        StageStates.Init(ENLLevelStageState::Available, RuntimeStages.Num());
        FailureReason = NAME_None;
        BlockedStageId = EntryBlockReason = NAME_None;
    }
    ObservedRunId = RunId;
    // A durable first defeat also owns its automatically collected seal. Older v2 ledgers migrate naturally.
    // Do not complete an active stage reentrantly while its final death callback is still running.
    for (int32 Index = 0; Index < RuntimeStages.Num(); ++Index)
        if (StageStates[Index] == ENLLevelStageState::Available && !RuntimeStages[Index].SealId.IsNone()
            && BoundRunState->HasSeal(RuntimeStages[Index].SealId))
            SetStageState(Index, ENLLevelStageState::Completed);
}

TArray<FName> ANLLevelEncounterDirector::GetMissingSealIds(FName StageId) const
{
    TArray<FName> Missing;
    const int32 Index = FindStageIndex(StageId);
    if (!RuntimeStages.IsValidIndex(Index)) return Missing;
    const UNLRunStateSubsystem* State = ResolveRunState();
    for (FName SealId : RuntimeStages[Index].RequiredSealIds)
        if (!State || !State->HasSeal(SealId)) Missing.Add(SealId);
    return Missing;
}

FName ANLLevelEncounterDirector::GetBlockedStageId() const
{
    return GetWorld() && EntryBlockedAt >= 0.0 && GetWorld()->GetTimeSeconds() - EntryBlockedAt < 3.0
        ? BlockedStageId : NAME_None;
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
    return StageStates[Index] == ENLLevelStageState::Available
        && (!HasClearedDependency(Index) || !GetMissingSealIds(StageId).IsEmpty())
        ? ENLLevelStageState::Locked : StageStates[Index];
}

ANLEncounterController* ANLLevelEncounterDirector::GetActiveEncounter() const
{
    return IsValid(ActiveEncounter) && !ActiveEncounter->IsActorBeingDestroyed() ? ActiveEncounter.Get() : nullptr;
}

ANLRitualObjective* ANLLevelEncounterDirector::GetActiveObjective() const
{
    ANLRitualObjective* Objective = ActiveObjective.Get();
    return IsValid(Objective) && !Objective->IsActorBeingDestroyed() ? Objective : nullptr;
}

ANLRitualObjective* ANLLevelEncounterDirector::FindStageObjective(int32 Index, FName& OutReason) const
{
    OutReason = NAME_None;
    if (!RuntimeStages.IsValidIndex(Index)) { OutReason = TEXT("InvalidObjectiveStage"); return nullptr; }
    const FName Id = RuntimeStages[Index].ObjectiveStableId;
    if (Id.IsNone()) return nullptr;
    ANLRitualObjective* Result = nullptr;
    if (GetWorld())
        for (TActorIterator<ANLRitualObjective> It(GetWorld()); It; ++It)
            if (!It->IsActorBeingDestroyed() && It->ObjectiveStableId == Id)
            {
                if (Result) { OutReason = TEXT("DuplicateStageObjective"); return nullptr; }
                Result = *It;
            }
    if (!Result) OutReason = TEXT("MissingStageObjective");
    return Result;
}

bool ANLLevelEncounterDirector::PreflightStageObjective(int32 Index, bool bRetry,
    ANLRitualObjective*& OutObjective, FNLObjectiveSnapshot& OutSnapshot, FName& OutReason) const
{
    OutSnapshot = FNLObjectiveSnapshot();
    OutObjective = FindStageObjective(Index, OutReason);
    if (!OutReason.IsNone()) return false;
    if (!OutObjective) return true;
    if (bRetry)
    {
        if (OutObjective != GetActiveObjective()) { OutReason = TEXT("StageObjectiveChanged"); return false; }
        OutSnapshot = EntryObjective;
    }
    else
    {
        const FNLLevelEncounterStage& Stage = RuntimeStages[Index];
        if (Stage.bContinueObjectiveFromPreviousStage)
        {
            const FNLObjectiveSnapshot* Previous = CompletedObjectiveSnapshots.Find(Stage.RequiredStageId);
            const TWeakObjectPtr<ANLRitualObjective>* PreviousObjectiveOwner = CompletedObjectiveOwners.Find(Stage.RequiredStageId);
            const int32 PreviousIndex = FindStageIndex(Stage.RequiredStageId);
            if (!Previous || !PreviousObjectiveOwner || PreviousObjectiveOwner->Get() != OutObjective || !StageStates.IsValidIndex(PreviousIndex)
                || StageStates[PreviousIndex] != ENLLevelStageState::Completed
                || !FMath::IsNearlyEqual(Previous->RescueProgress, RuntimeStages[PreviousIndex].ObjectiveProgressTarget))
            {
                OutReason = TEXT("MissingCompletedObjectivePhase");
                return false;
            }
            OutSnapshot = *Previous;
        }
        else
        {
            OutSnapshot.StableId = Stage.ObjectiveStableId;
            OutSnapshot.Integrity = OutObjective->MaxIntegrity;
        }
    }
    const float ProgressTarget = RuntimeStages[Index].ObjectiveProgressTarget;
    if (!OutObjective->CanRestoreObjectivePhaseSnapshot(OutSnapshot, ProgressTarget, OutReason)) return false;
    if (OutSnapshot.Integrity <= 0.0f || OutSnapshot.bCompleted || OutSnapshot.RescueProgress >= ProgressTarget
        || !OutSnapshot.InterferenceSourceIds.IsEmpty())
    {
        OutReason = TEXT("InvalidObjectiveStageEntry");
        return false;
    }
    return true;
}

bool ANLLevelEncounterDirector::CanRetryActiveStage(FName& OutReason) const
{
    OutReason = NAME_None;
    if (!bConfigurationValid || bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || (StageStates[ActiveStageIndex] != ENLLevelStageState::Failed
            && StageStates[ActiveStageIndex] != ENLLevelStageState::Active
            && StageStates[ActiveStageIndex] != ENLLevelStageState::Warning))
    {
        OutReason = TEXT("NoRetryableStage");
        return false;
    }
    ANLRitualObjective* Objective = nullptr;
    FNLObjectiveSnapshot Snapshot;
    return PreflightStageObjective(ActiveStageIndex, true, Objective, Snapshot, OutReason);
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
        ? FMath::Max(0.0f, WarningSecondsRemaining) : 0.0f;
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

bool ANLLevelEncounterDirector::IsPlayerReadyForStage(const APawn* Pawn) const
{
    const ANLDesktopPlayerCharacter* Player = Cast<ANLDesktopPlayerCharacter>(Pawn);
    // Native fixture pawns and desktop players need no tracked-device preparation.
    // VR supplies the physical tracking/mapping/recenter/readiness policy through this interface.
    return !Player || Player->IsReadyForLevelEncounter();
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
        || !IsLivingPlayer(TriggeringPawn)
        || !IsStageInside(Index, TriggeringPawn->GetActorLocation())) return false;
    const UNLRunStateSubsystem* Run = ResolveRunState();
    if ((!RuntimeStages[Index].SealId.IsNone() || !RuntimeStages[Index].RequiredSealIds.IsEmpty())
        && (!Run || !Run->IsQuestProgressAvailable()))
    {
        BlockedStageId = StageId;
        EntryBlockReason = TEXT("SealProgressUnavailable");
        EntryBlockedAt = GetWorld()->GetTimeSeconds();
        return false;
    }
    if (!GetMissingSealIds(StageId).IsEmpty())
    {
        BlockedStageId = StageId;
        EntryBlockReason = TEXT("MissingRequiredSeals");
        EntryBlockedAt = GetWorld()->GetTimeSeconds();
        return false;
    }
    if (GetStageStatus(StageId) != ENLLevelStageState::Available) return false;
    BlockedStageId = EntryBlockReason = NAME_None;
    return BeginWarning(Index, TriggeringPawn);
}

bool ANLLevelEncounterDirector::BeginWarning(int32 Index, APawn* Pawn)
{
    if (!StageStates.IsValidIndex(Index) || !IsLivingPlayer(Pawn)) return false;
    const bool bRetry = ActiveStageIndex == Index && StageStates[Index] == ENLLevelStageState::Failed;
    ANLRitualObjective* Objective = nullptr;
    FNLObjectiveSnapshot ObjectiveSnapshot;
    FName ObjectiveReason;
    if (!PreflightStageObjective(Index, bRetry, Objective, ObjectiveSnapshot, ObjectiveReason))
    {
        BlockedStageId = RuntimeStages[Index].StageId;
        EntryBlockReason = ObjectiveReason;
        EntryBlockedAt = GetWorld()->GetTimeSeconds();
        return false;
    }
    if (!bRetry)
    {
        EntryProgression = FNLProgressionState();
        bHasEntryProgression = false;
        if (const UNLRunStateSubsystem* State = ResolveRunState(); State && State->GetRunId().IsValid())
        {
            EntryProgression = State->GetProgressionState();
            bHasEntryProgression = true;
        }
        EntryBurstEnergy = EntryProgression.BurstEnergy;
        if (RuntimeUpgradeDefinition && !bHasEntryProgression)
        {
            FailureReason = TEXT("ProgressionRunUnavailable");
            return false;
        }
    }
    TGuardValue<bool> EntryGuard(bChangingEncounter, true);
    const UNLRunStateSubsystem* EntryRun = ResolveRunState();
    const FGuid EntryRunId = EntryRun ? EntryRun->GetRunId() : FGuid();
    bRetryProgressionPrepared = false;
    ReleasePlayerBinding();
    ReleaseObjective();
    ReleaseEncounter();
    EntryObjective = ObjectiveSnapshot;
    ActiveObjective = Objective;
    if (Objective)
    {
        const auto IsEntryCurrent = [this, Objective, Index, EntryRunId]()
        {
            FName CurrentObjectiveReason;
            const UNLRunStateSubsystem* CurrentRun = ResolveRunState();
            return IsValid(Objective) && !Objective->IsActorBeingDestroyed()
                && FindStageObjective(Index, CurrentObjectiveReason) == Objective && CurrentObjectiveReason.IsNone()
                && (CurrentRun ? CurrentRun->GetRunId() : FGuid()) == EntryRunId;
        };
        // Restore clears all old threats/source bindings after the old encounter and its shots are removed.
        if (!IsEntryCurrent() || !Objective->RestoreObjectivePhaseSnapshot(EntryObjective, RuntimeStages[Index].ObjectiveProgressTarget)
            || !IsEntryCurrent())
        {
            ReleaseObjective();
            FailureReason = TEXT("ObjectiveEntryRestoreFailed");
            return false;
        }
        Objective->FinishSourceRebuild();
        if (IsEntryCurrent()) Objective->SetObjectiveActive(false);
        // Objective restore/change delegates are synchronous and may destroy/rename it
        // or explicitly start a different run. Do not commit the old phase after that.
        if (!IsEntryCurrent())
        {
            ReleaseObjective();
            FailureReason = TEXT("ObjectiveEntryChangedDuringRestore");
            return false;
        }
        Objective->OnCompletionPending.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleObjectiveCompletionPending);
        Objective->OnBeforeCompletionCheck.AddUniqueDynamic(this, &ANLLevelEncounterDirector::RefreshObjectiveThreats);
        Objective->OnRescueCompleted.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleObjectiveCompleted);
        Objective->OnPhaseCompleted.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleObjectivePhaseCompleted);
        Objective->OnObjectiveFailed.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleObjectiveFailed);
    }
    ActiveStageIndex = Index;
    ActivePlayer = Pawn;
    ActiveVitals = Pawn->FindComponentByClass<UNLCombatVitalsComponent>();
    ActiveVitals->OnDied.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandlePlayerDied);
    FailureReason = NAME_None;
    WarningSecondsRemaining = RuntimeStages[Index].WarningSeconds;
    SetStageState(Index, ENLLevelStageState::Warning);
    UE_LOG(LogNLLevelEncounter, Log, TEXT("%s stage %s warning %.2fs"), *GetName(), *GetActiveStageId().ToString(), RuntimeStages[Index].WarningSeconds);
    return true;
}

void ANLLevelEncounterDirector::StartActiveEncounter()
{
    if (!StageStates.IsValidIndex(ActiveStageIndex) || StageStates[ActiveStageIndex] != ENLLevelStageState::Warning || bChangingEncounter) return;
    if (!IsLivingPlayer(ActivePlayer.Get())) { FailActiveStage(TEXT("PlayerDied")); return; }
    if (!IsPlayerReadyForStage(ActivePlayer.Get())) return;
    const int32 StartingIndex = ActiveStageIndex;
    const FNLLevelEncounterStage Stage = RuntimeStages[StartingIndex];
    const TWeakObjectPtr<APawn> StartingPlayer = ActivePlayer;
    const TWeakObjectPtr<ANLRitualObjective> StartingObjective = ActiveObjective;
    const UNLRunStateSubsystem* StartingRun = ResolveRunState();
    const FGuid StartingRunId = StartingRun ? StartingRun->GetRunId() : FGuid();
    const auto IsStartingStageCurrent = [this, StartingIndex, StartingPlayer, StartingObjective, StartingRunId](ENLLevelStageState Expected)
    {
        const UNLRunStateSubsystem* CurrentRun = ResolveRunState();
        return !bEndingPlay && ActiveStageIndex == StartingIndex && StageStates.IsValidIndex(StartingIndex)
            && StageStates[StartingIndex] == Expected && ActivePlayer == StartingPlayer && ActiveObjective == StartingObjective
            && (CurrentRun ? CurrentRun->GetRunId() : FGuid()) == StartingRunId;
    };
    if (!Stage.ObjectiveStableId.IsNone())
    {
        FName Reason;
        if (FindStageObjective(ActiveStageIndex, Reason) != GetActiveObjective() || !Reason.IsNone()
            || !GetActiveObjective() || !GetActiveObjective()->CanRestoreObjectivePhaseSnapshot(EntryObjective, Stage.ObjectiveProgressTarget, Reason))
        { FailActiveStage(Reason.IsNone() ? FName(TEXT("StageObjectiveChanged")) : Reason); return; }
    }
    const FTransform Transform = FTransform::Identity;
    ANLEncounterController* Encounter = GetWorld()->SpawnActorDeferred<ANLEncounterController>(ANLEncounterController::StaticClass(),
        Transform, this, ActivePlayer.Get(), ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!IsStartingStageCurrent(ENLLevelStageState::Warning))
    {
        if (IsValid(Encounter)) Encounter->Destroy();
        return;
    }
    if (!Encounter) { FailActiveStage(TEXT("EncounterSpawnFailed")); return; }
    Encounter->Waves = Stage.Waves;
    Encounter->SpawnPoints = Stage.SpawnPoints;
    Encounter->Seed = Stage.Seed;
    Encounter->LevelId = LevelId;
    Encounter->EncounterId = Stage.StageId;
    Encounter->bEnableCheckpoints = false;
    Encounter->bDeferCompletionToObjective = !Stage.ObjectiveStableId.IsNone();
    Encounter->bShowReadyPreviews = false;
    Encounter->bShowStagingQueue = true;
    ActiveEncounter = Encounter;
    Encounter->FinishSpawning(Transform);
    if (!IsStartingStageCurrent(ENLLevelStageState::Warning) || ActiveEncounter != Encounter)
    {
        if (IsValid(Encounter) && !Encounter->IsActorBeingDestroyed()) Encounter->Destroy();
        return;
    }
    if (!IsValid(Encounter) || Encounter->IsActorBeingDestroyed()) { FailActiveStage(TEXT("EncounterSpawnFailed")); return; }
    Encounter->OnEncounterCompleted.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleEncounterCompleted);
    Encounter->OnEncounterFailed.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleEncounterFailed);
    Encounter->OnEnemyDefeated.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleEnemyDefeated);
    Encounter->OnPauseChanged.AddUniqueDynamic(this, &ANLLevelEncounterDirector::HandleEncounterPauseChanged);
    // BeginPlay validates the full wave plan before the event bindings above exist.
    if (Encounter->GetState() == ENLEncounterState::Failed) { FailActiveStage(Encounter->GetFailureReason()); return; }
    SetStageState(StartingIndex, ENLLevelStageState::Active);
    // These broadcasts can explicitly begin another run, which clears the stage index
    // and destroys the old encounter. Never index or activate using that stale start.
    if (!IsStartingStageCurrent(ENLLevelStageState::Active) || GetActiveEncounter() != Encounter
        || !IsLivingPlayer(StartingPlayer.Get())) return;
    Encounter->StartEncounter();
    if (IsStartingStageCurrent(ENLLevelStageState::Active) && GetActiveEncounter() == Encounter)
        if (ANLRitualObjective* Objective = GetActiveObjective()) Objective->SetObjectiveActive(true);
}

void ANLLevelEncounterDirector::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bConfigurationValid || bEndingPlay || bChangingEncounter || !GetWorld() || GetWorld()->IsPaused()) return;
    if (IsBusy())
    {
        const ENLLevelStageState State = StageStates[ActiveStageIndex];
        if (State == ENLLevelStageState::Failed) return;
        if (!RuntimeStages[ActiveStageIndex].ObjectiveStableId.IsNone())
        {
            FName Reason;
            if (!GetActiveObjective() || FindStageObjective(ActiveStageIndex, Reason) != GetActiveObjective() || !Reason.IsNone())
            { FailActiveStage(Reason.IsNone() ? FName(TEXT("StageObjectiveChanged")) : Reason); return; }
        }
        if (!IsLivingPlayer(ActivePlayer.Get())) { FailActiveStage(TEXT("PlayerDied")); return; }
        if (State == ENLLevelStageState::Warning)
        {
            // Readiness loss freezes this warning; it neither restarts the stage nor consumes its entry snapshot.
            if (!IsPlayerReadyForStage(ActivePlayer.Get())) return;
            if (FMath::IsFinite(DeltaSeconds) && DeltaSeconds > 0.0f)
                WarningSecondsRemaining = FMath::Max(0.0f, WarningSecondsRemaining - DeltaSeconds);
            if (GetWarningRemaining() <= 0.0f) StartActiveEncounter();
        }
        else if (!GetActiveEncounter()) FailActiveStage(TEXT("EncounterRemoved"));
        return;
    }
    APawn* Pawn = FindPlayerPawn();
    if (!Pawn || !IsPlayerReadyForStage(Pawn)) return;
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
    // Both stage and objective delegates run synchronously. Commit the terminal state
    // while retry/entry mutations are locked before either delegate can call back here.
    TGuardValue<bool> TransitionGuard(bChangingEncounter, true);
    bRetryProgressionPrepared = false;
    FailureReason = Reason.IsNone() ? FName(TEXT("EncounterFailed")) : Reason;
    WarningSecondsRemaining = 0.0f;
    SetStageState(ActiveStageIndex, ENLLevelStageState::Failed);
    if (ANLRitualObjective* Objective = GetActiveObjective()) Objective->SetCombatPaused(true);
    if (ANLEncounterController* Encounter = GetActiveEncounter()) Encounter->FailEncounter(FailureReason);
    UE_LOG(LogNLLevelEncounter, Warning, TEXT("%s stage %s failed: %s"), *GetName(), *GetActiveStageId().ToString(), *FailureReason.ToString());
}

bool ANLLevelEncounterDirector::RestoreRetryProgression()
{
    if (!bConfigurationValid || bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Failed) return false;
    FName Reason;
    if (!CanRetryActiveStage(Reason)) { FailureReason = Reason; return false; }
    bRetryProgressionPrepared = false;
    UNLRunStateSubsystem* State = ResolveRunState();
    if (!bHasEntryProgression)
    {
        if (RuntimeUpgradeDefinition) return false;
        bRetryProgressionPrepared = true;
        PreparedRetryStageIndex = ActiveStageIndex;
        PreparedRetryRunId = State ? State->GetRunId() : FGuid();
        PreparedRetryObjective = ActiveObjective;
        return true;
    }
    if (!State)
    {
        FailureReason = TEXT("ProgressionRunUnavailable");
        return false;
    }
    const int32 ExpectedStageIndex = ActiveStageIndex;
    const FName ExpectedStageId = GetActiveStageId();
    const FGuid ExpectedRunId = State->GetRunId();
    const TWeakObjectPtr<ANLRitualObjective> ExpectedObjective = ActiveObjective;
    const FNLProgressionState BeforeProgression = State->GetProgressionState();
    const auto RollbackGrowthAndReject = [this, State, ExpectedRunId, &BeforeProgression](FName Rejection)
    {
        // Only roll back state owned by this retry. An observer explicitly starting a new run
        // must not receive the old run's resources or reward ledger.
        if (State->GetRunId() == ExpectedRunId)
        {
            TGuardValue<bool> RollbackGuard(bChangingEncounter, true);
            if (!State->RestoreProgressionState(BeforeProgression))
            {
                FailureReason = TEXT("RetryProgressionRollbackFailed");
                return false;
            }
        }
        FailureReason = Rejection;
        return false;
    };
    bool bRestored = false;
    {
        // Run-state listeners may try to retry or enter a different stage. Those transitions
        // cannot proceed while growth is being restored, before the player is revived.
        TGuardValue<bool> TransitionGuard(bChangingEncounter, true);
        bRestored = State->RestoreProgressionState(EntryProgression);
    }
    if (!bRestored)
    {
        FailureReason = State->GetLastFailureReason();
        return false;
    }
    // A listener may still rename/destroy the objective or start a new run directly.
    // Fail before the caller changes player resources/transform; never continue with stale preflight.
    if (ActiveStageIndex != ExpectedStageIndex || GetActiveStageId() != ExpectedStageId
        || !StageStates.IsValidIndex(ActiveStageIndex) || StageStates[ActiveStageIndex] != ENLLevelStageState::Failed
        || State->GetRunId() != ExpectedRunId || ActiveObjective != ExpectedObjective)
    {
        return RollbackGrowthAndReject(TEXT("RetryStageChangedDuringProgressionRestore"));
    }
    if (!CanRetryActiveStage(Reason)) return RollbackGrowthAndReject(Reason);
    bRetryProgressionPrepared = true;
    PreparedRetryStageIndex = ExpectedStageIndex;
    PreparedRetryRunId = ExpectedRunId;
    PreparedRetryObjective = ExpectedObjective;
    return true;
}

bool ANLLevelEncounterDirector::RetryActiveStage()
{
    if (!bConfigurationValid || bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Failed || !GetWorld() || GetWorld()->IsPaused()) return false;
    APawn* Pawn = IsLivingPlayer(ActivePlayer.Get()) ? ActivePlayer.Get() : FindPlayerPawn();
    if (!Pawn) return false;
    FName Reason;
    if (!CanRetryActiveStage(Reason)) { FailureReason = Reason; return false; }
    const UNLRunStateSubsystem* Run = ResolveRunState();
    const bool bPrepared = bRetryProgressionPrepared && PreparedRetryStageIndex == ActiveStageIndex
        && PreparedRetryRunId == (Run ? Run->GetRunId() : FGuid()) && PreparedRetryObjective == ActiveObjective;
    if (!bPrepared && !RestoreRetryProgression()) return false;
    bRetryProgressionPrepared = false;
    const FNLLevelEncounterStage& Stage = RuntimeStages[ActiveStageIndex];
    if (!Stage.SealId.IsNone())
        if (const UNLRunStateSubsystem* State = ResolveRunState(); State && State->HasSeal(Stage.SealId))
        {
            ReleasePlayerBinding();
            ReleaseEncounter();
            FailureReason = NAME_None;
            SetStageState(ActiveStageIndex, ENLLevelStageState::Completed);
            return true;
        }
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
    if (!RuntimeStages[ActiveStageIndex].ObjectiveStableId.IsNone()) return;
    CompleteActiveStage();
}

void ANLLevelEncounterDirector::CompleteActiveStage()
{
    if (bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Active) return;
    if (!IsLivingPlayer(ActivePlayer.Get())) { FailActiveStage(TEXT("PlayerDied")); return; }
    const int32 ClearedIndex = ActiveStageIndex;
    const TWeakObjectPtr<ANLEncounterController> CompletingEncounter = ActiveEncounter;
    const TWeakObjectPtr<ANLRitualObjective> CompletingObjective = ActiveObjective;
    const int32 MinimumUpgradeLevel = RuntimeStages[ClearedIndex].MinimumUpgradeLevelOnComplete;
    if (MinimumUpgradeLevel > 1)
    {
        UNLRunStateSubsystem* State = ResolveRunState();
        const FGuid CompletingRunId = State ? State->GetRunId() : FGuid();
        if (!State || !State->EnsureUpgradeLevel(MinimumUpgradeLevel))
        {
            FailActiveStage(TEXT("UpgradeGuaranteeFailed"));
            return;
        }
        // Upgrade notifications are synchronous. A listener may start a new run
        // or replace the encounter; the old completion must not commit into it.
        if (bEndingPlay || State != ResolveRunState() || State->GetRunId() != CompletingRunId
            || ActiveStageIndex != ClearedIndex || !StageStates.IsValidIndex(ClearedIndex)
            || StageStates[ClearedIndex] != ENLLevelStageState::Active
            || ActiveEncounter != CompletingEncounter || ActiveObjective != CompletingObjective)
            return;
    }
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
        || !Enemy->CombatIdentity || Enemy->CombatIdentity->GetRuntimeId() != EnemyRuntimeId
        || !EnemyRuntimeId.IsValid() || SpawnOrdinal < 0 || !Enemy->Vitals || !Enemy->Vitals->IsDead()) return;
    const int32 DefeatStageIndex = ActiveStageIndex;
    const FNLLevelEncounterStage DefeatStage = RuntimeStages[DefeatStageIndex];
    const TWeakObjectPtr<ANLEncounterController> DefeatEncounter = ActiveEncounter;
    const TWeakObjectPtr<APawn> DefeatPlayer = ActivePlayer;
    UNLRunStateSubsystem* DefeatRun = ResolveRunState();
    const FGuid DefeatRunId = DefeatRun ? DefeatRun->GetRunId() : FGuid();
    const auto IsDefeatCurrent = [this, DefeatStageIndex, DefeatEncounter, DefeatPlayer, DefeatRun, DefeatRunId]()
    {
        const UNLRunStateSubsystem* CurrentRun = ResolveRunState();
        return !bEndingPlay && !bChangingEncounter && ActiveStageIndex == DefeatStageIndex
            && StageStates.IsValidIndex(DefeatStageIndex) && StageStates[DefeatStageIndex] == ENLLevelStageState::Active
            && DefeatEncounter.IsValid() && GetActiveEncounter() == DefeatEncounter.Get()
            && ActivePlayer == DefeatPlayer && IsLivingPlayer(DefeatPlayer.Get())
            && CurrentRun == DefeatRun && (CurrentRun ? CurrentRun->GetRunId() : FGuid()) == DefeatRunId;
    };
    const FName EventId(*FString::Printf(TEXT("%s.%s.Wave.%02d.Spawn.%04d"),
        *LevelId.ToString(), *DefeatStage.StageId.ToString(), DefeatEncounter->GetWaveIndex() + 1, SpawnOrdinal));
    if (RuntimeUpgradeDefinition)
    {
        if (!DefeatRun) { FailActiveStage(TEXT("LingQiRewardFailed")); return; }
        const bool bAwarded = DefeatRun->AwardLingQi(EventId, DefeatRun->GetLingQiPerDefeat());
        // A real defeat reward broadcasts synchronously. A listener may begin another
        // run, clearing the stage index and destroying this encounter before we return.
        if (!IsDefeatCurrent()) return;
        if (!bAwarded && !DefeatRun->GetLastFailureReason().IsNone())
        {
            FailActiveStage(TEXT("LingQiRewardFailed"));
            return;
        }
    }
    if (RuntimeUpgradeDefinition && bEnableOrdinarySupplies
        && IsOrdinarySupplyEligible(DefeatStage, SpawnOrdinal, DefeatEncounter->GetPlannedCount(),
            DefeatEncounter->GetWaveIndex(), DefeatEncounter->GetWaveCount()))
    {
        UNLOrdinaryLootSubsystem* Loot = GetWorld()->GetSubsystem<UNLOrdinaryLootSubsystem>();
        const bool bCommitted = Loot && Loot->RecordEligibleDefeat(EventId, Enemy->GetActorLocation() - FVector(0, 0, 60));
        if (!IsDefeatCurrent()) return;
        if (!bCommitted) { FailActiveStage(TEXT("OrdinaryLootCommitFailed")); return; }
    }
    const FName MasterId = DefeatStage.MasterId;
    if (MasterId.IsNone() || RewardedMasters.Contains(MasterId)
        || !IsFinalWaveFinalOrdinal(SpawnOrdinal, DefeatEncounter->GetPlannedCount(),
            DefeatEncounter->GetWaveIndex(), DefeatEncounter->GetWaveCount())) return;
    const FName SealId = DefeatStage.SealId;
    if (!SealId.IsNone())
    {
        UNLRunStateSubsystem* State = ResolveRunState();
        if (!State) { FailActiveStage(TEXT("SealProgressionCommitFailed")); return; }
        const bool bHasSeal = State->HasSeal(SealId)
            || State->GrantMasterSeal(MasterId, SealId, Enemy->GetActorLocation() - FVector(0, 0, 40));
        if (!IsDefeatCurrent()) return;
        if (!bHasSeal)
        {
            FailActiveStage(TEXT("SealProgressionCommitFailed"));
            return;
        }
    }
    RewardedMasters.Add(MasterId);
    OnMasterDefeated.Broadcast(MasterId, Enemy->GetActorLocation());
}

bool ANLLevelEncounterDirector::IsFinalWaveFinalOrdinal(int32 SpawnOrdinal, int32 PlannedCount, int32 WaveIndex, int32 WaveCount)
{
    // Ordinals are assigned across the complete authored wave order by NLEncounterController.
    // Requiring both facts prevents an earlier disciple from consuming the master's first-kill reward.
    return PlannedCount > 0 && WaveCount > 0 && SpawnOrdinal == PlannedCount - 1 && WaveIndex == WaveCount - 1;
}

bool ANLLevelEncounterDirector::IsOrdinarySupplyEligible(const FNLLevelEncounterStage& Stage,
    int32 SpawnOrdinal, int32 PlannedCount, int32 WaveIndex, int32 WaveCount)
{
    if (Stage.StageId == TEXT("Boss") || SpawnOrdinal < 0 || SpawnOrdinal >= PlannedCount
        || WaveIndex < 0 || WaveIndex >= WaveCount) return false;
    return Stage.MasterId.IsNone() || !IsFinalWaveFinalOrdinal(SpawnOrdinal, PlannedCount, WaveIndex, WaveCount);
}

void ANLLevelEncounterDirector::ReleasePlayerBinding()
{
    if (UNLCombatVitalsComponent* Vitals = ActiveVitals.Get())
        Vitals->OnDied.RemoveDynamic(this, &ANLLevelEncounterDirector::HandlePlayerDied);
    ActiveVitals.Reset();
    ActivePlayer.Reset();
}

void ANLLevelEncounterDirector::ReleaseObjective()
{
    ANLRitualObjective* Objective = GetActiveObjective();
    ActiveObjective.Reset();
    if (!Objective) return;
    Objective->OnCompletionPending.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleObjectiveCompletionPending);
    Objective->OnBeforeCompletionCheck.RemoveDynamic(this, &ANLLevelEncounterDirector::RefreshObjectiveThreats);
    Objective->OnRescueCompleted.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleObjectiveCompleted);
    Objective->OnPhaseCompleted.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleObjectivePhaseCompleted);
    Objective->OnObjectiveFailed.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleObjectiveFailed);
    Objective->SetObjectiveActive(false);
}

void ANLLevelEncounterDirector::RefreshObjectiveThreats(ANLRitualObjective* Objective)
{
    if (bEndingPlay || bChangingEncounter || Objective != GetActiveObjective()
        || !StageStates.IsValidIndex(ActiveStageIndex) || StageStates[ActiveStageIndex] != ENLLevelStageState::Active) return;
    FName Reason;
    if (FindStageObjective(ActiveStageIndex, Reason) != Objective || !Reason.IsNone())
    { FailActiveStage(Reason.IsNone() ? FName(TEXT("StageObjectiveChanged")) : Reason); return; }
    ANLEncounterController* Encounter = GetActiveEncounter();
    if (!Encounter) { FailActiveStage(TEXT("EncounterRemoved")); return; }
    if (!IsLivingPlayer(ActivePlayer.Get())) { FailActiveStage(TEXT("PlayerDied")); return; }
    // Called synchronously by the objective before its completion check, so a newly fired
    // projectile cannot fall into a gap between the level director's coarse Tick and rescue.
    for (TActorIterator<ANLEnemyCharacter> It(GetWorld()); It; ++It)
        if (Encounter->OwnsEnemy(*It) && It->CombatIdentity && It->Vitals && !It->Vitals->IsDead())
            Objective->RegisterRemainingThreat(FName(*FString::Printf(TEXT("Enemy.%s"),
                *It->CombatIdentity->GetRuntimeId().ToString(EGuidFormats::Digits))), *It);
    for (TActorIterator<ANLCombatProjectile> It(GetWorld()); It; ++It)
    {
        // Possession makes an enemy pawn's Actor Owner its AIController. The encounter's
        // spawn records, rather than Actor ownership, remain authoritative after caster death.
        const ANLEnemyCharacter* Source = Cast<ANLEnemyCharacter>(It->GetSourceActor());
        if (Encounter->OwnsEnemy(Source))
            Objective->RegisterRemainingThreat(FName(*FString::Printf(TEXT("Projectile.%s.%d"),
                *It->GetAttackInstanceId().ToString(EGuidFormats::Digits), It->GetUniqueID())), *It);
    }
}

void ANLLevelEncounterDirector::HandleObjectiveCompletionPending(ANLRitualObjective* Objective)
{
    if (Objective != GetActiveObjective() || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Active) return;
    if (ANLEncounterController* Encounter = GetActiveEncounter()) Encounter->StopSpawningForObjective();
    RefreshObjectiveThreats(Objective);
}

void ANLLevelEncounterDirector::HandleObjectiveCompleted(ANLRitualObjective* Objective)
{
    if (Objective != GetActiveObjective() || !Objective->IsRescueCompleted()
        || Objective->IsFailureLocked() || Objective->GetIntegrity() <= 0.0f) return;
    FinishObjectiveStage(Objective);
}

void ANLLevelEncounterDirector::HandleObjectivePhaseCompleted(ANLRitualObjective* Objective)
{
    if (Objective != GetActiveObjective() || !Objective->IsPhaseCompleted()
        || Objective->IsRescueCompleted() || Objective->IsFailureLocked() || Objective->GetIntegrity() <= 0.0f) return;
    FinishObjectiveStage(Objective);
}

void ANLLevelEncounterDirector::FinishObjectiveStage(ANLRitualObjective* Objective)
{
    if (bEndingPlay || bChangingEncounter || !StageStates.IsValidIndex(ActiveStageIndex)
        || StageStates[ActiveStageIndex] != ENLLevelStageState::Active) return;
    const int32 CompletedIndex = ActiveStageIndex;
    const FNLLevelEncounterStage& Stage = RuntimeStages[CompletedIndex];
    if (!FMath::IsNearlyEqual(Objective->GetRescueProgress(), Stage.ObjectiveProgressTarget)
        || Objective->GetProgressTarget() != Stage.ObjectiveProgressTarget) return;
    const FNLObjectiveSnapshot Snapshot = Objective->CaptureObjectiveSnapshot();
    const TWeakObjectPtr<ANLEncounterController> CompletedEncounter = GetActiveEncounter();
    const UNLRunStateSubsystem* CompletingState = ResolveRunState();
    const FGuid CompletingRunId = CompletingState ? CompletingState->GetRunId() : FGuid();
    // Publish a durable-in-run exit before stage observers can request the next stage.
    CompletedObjectiveSnapshots.Add(Stage.StageId, Snapshot);
    CompletedObjectiveOwners.Add(Stage.StageId, Objective);
    CompleteActiveStage();
    // A completion reward or stage notification can replace the run synchronously.
    // Its snapshots now belong to that new run, even if the stage IDs are identical.
    if (bEndingPlay || CompletingState != ResolveRunState()
        || (CompletingState && CompletingState->GetRunId() != CompletingRunId)) return;
    if (StageStates.IsValidIndex(CompletedIndex) && StageStates[CompletedIndex] == ENLLevelStageState::Completed)
    {
        // A synchronous stage listener may have activated a different encounter. Never cancel that one.
        if (CompletedEncounter.IsValid()) CompletedEncounter->CancelEncounter();
    }
    else
    {
        CompletedObjectiveSnapshots.Remove(Stage.StageId);
        CompletedObjectiveOwners.Remove(Stage.StageId);
    }
}

void ANLLevelEncounterDirector::HandleObjectiveFailed(ANLRitualObjective* Objective)
{
    if (Objective == GetActiveObjective()) FailActiveStage(TEXT("RitualIntegrityDepleted"));
}

void ANLLevelEncounterDirector::HandleEncounterPauseChanged(bool bPaused)
{
    if (!StageStates.IsValidIndex(ActiveStageIndex)) return;
    if (ANLRitualObjective* Objective = GetActiveObjective())
        Objective->SetCombatPaused(bPaused || StageStates[ActiveStageIndex] != ENLLevelStageState::Active);
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
    Encounter->OnPauseChanged.RemoveDynamic(this, &ANLLevelEncounterDirector::HandleEncounterPauseChanged);
    Encounter->CancelEncounter();
    Encounter->Destroy();
}

void ANLLevelEncounterDirector::SetStageState(int32 Index, ENLLevelStageState State)
{
    if (!StageStates.IsValidIndex(Index) || StageStates[Index] == State) return;
    StageStates[Index] = State;
    if (!bEndingPlay) OnStageChanged.Broadcast(RuntimeStages[Index].StageId, State);
}
