#include "Encounter/NLEncounterController.h"

#include "AIController.h"
#include "AI/NLAttackDirectorSubsystem.h"
#include "AI/NLEnemyBrainComponent.h"
#include "AI/NLEnemyCharacter.h"
#include "Animation/AnimSequenceBase.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Encounter/NLWaveDefinition.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"

DEFINE_LOG_CATEGORY_STATIC(LogNLEncounter, Log, All);

namespace
{
    constexpr int32 MaximumPlannedEnemies = 1024;
    constexpr int32 MaximumPlannedEnemiesPerWave = 512;
    constexpr int32 MaximumSpawnRetries = 32;
    constexpr int32 MaximumAliveEnemies = 12;

    bool IsValidDuration(float Value)
    {
        return FMath::IsFinite(Value) && Value >= 0.0f;
    }

    bool NameBefore(FName Left, FName Right)
    {
        return Left.ToString().Compare(Right.ToString(), ESearchCase::CaseSensitive) < 0;
    }
}

ANLEncounterController::ANLEncounterController()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bTickEvenWhenPaused = false;
    // BeginPlay only validates the configuration; the player explicitly starts it.
}

void ANLEncounterController::BeginPlay()
{
    Super::BeginPlay();
    ResetProgress(Seed);
    FName Reason;
    if (!BuildPlan(Reason))
    {
        FailEncounter(Reason);
    }
}

void ANLEncounterController::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    bEndingPlay = true;
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    Super::EndPlay(EndPlayReason);
}

bool ANLEncounterController::IsRunning() const
{
    return State == ENLEncounterState::Spawning || State == ENLEncounterState::WaitingClear
        || State == ENLEncounterState::Intermission;
}

bool ANLEncounterController::OwnsEnemy(const ANLEnemyCharacter* Enemy) const
{
    return Enemy && FindOwnedEnemy(Enemy) != nullptr;
}

int32 ANLEncounterController::GetWaveCount() const
{
    return RuntimeWaves.IsEmpty() ? Waves.Num() : RuntimeWaves.Num();
}

int32 ANLEncounterController::GetAliveCount() const
{
    int32 Count = 0;
    for (const FOwnedEnemy& Record : OwnedEnemies)
    {
        // Missing actors remain unresolved until the audit fails the encounter.
        if (Record.Generation == EncounterGeneration && Record.Terminal == EOwnedTerminal::Active)
        {
            ++Count;
        }
    }
    return Count;
}

int32 ANLEncounterController::GetCurrentWavePlannedCount() const
{
    return RuntimeWaves.IsValidIndex(CurrentWaveIndex) ? RuntimeWaves[CurrentWaveIndex].Plan.Num() : 0;
}

int32 ANLEncounterController::GetCurrentWaveSpawnedCount() const
{
    return RuntimeWaves.IsValidIndex(CurrentWaveIndex) ? RuntimeWaves[CurrentWaveIndex].SpawnedCount : 0;
}

float ANLEncounterController::GetIntermissionRemaining() const
{
    return State == ENLEncounterState::Intermission
        ? static_cast<float>(FMath::Max(0.0, IntermissionEndsAt - GetEncounterTime())) : 0.0f;
}

double ANLEncounterController::GetEncounterTime() const
{
    if (!GetWorld()) return 0.0;
    const double WorldTime = bEncounterPaused ? PauseBeganWorldTime : GetWorld()->GetTimeSeconds();
    return WorldTime - AccumulatedPauseSeconds;
}

void ANLEncounterController::ResetProgress(int32 InSeed)
{
    Seed = InitialSeed = InSeed;
    CompositionRandom.Initialize(InSeed);
    RuntimeWaves.Reset();
    RuntimeEnemyClasses.Reset();
    OwnedEnemies.Reset();
    CurrentWaveIndex = INDEX_NONE;
    PlannedCount = SpawnedCount = DefeatedCount = FailedSpawnCount = CompletedWaveCount = 0;
    NextSpawnAt = IntermissionEndsAt = 0.0;
    PauseBeganWorldTime = AccumulatedPauseSeconds = 0.0;
    FailureReason = NAME_None;
    bEncounterPaused = false;
    bTerminalOutcomeEmitted = false;
    bSpawnInProgress = false;
}

bool ANLEncounterController::BuildPlan(FName& OutFailure)
{
    OutFailure = TEXT("InvalidWaveConfig");
    auto Reject = [this](const FString& Detail)
    {
        UE_LOG(LogNLEncounter, Error, TEXT("%s: invalid wave configuration: %s"), *GetName(), *Detail);
        RuntimeWaves.Reset();
        RuntimeEnemyClasses.Reset();
        PlannedCount = 0;
        return false;
    };

    if (Waves.IsEmpty() || Waves.Num() > MaximumPlannedEnemies)
        return Reject(TEXT("Waves must contain between 1 and 1024 definitions."));
    if (!IsValidDuration(CorpseHoldSeconds))
        return Reject(TEXT("CorpseHoldSeconds must be finite and nonnegative."));
    if (MaxSpawnsPerTick < 1 || MaxSpawnsPerTick > MaximumAliveEnemies)
        return Reject(TEXT("MaxSpawnsPerTick must be between 1 and 12."));

    TMap<FName, FNLWaveSpawnPoint> PointsById;
    for (const FNLWaveSpawnPoint& Point : SpawnPoints)
    {
        const FVector Scale = Point.SpawnTransform.GetScale3D();
        if (Point.SpawnPointId.IsNone() || PointsById.Contains(Point.SpawnPointId))
            return Reject(TEXT("Spawn points require unique, nonempty SpawnPointId values."));
        if (Point.SpawnTransform.ContainsNaN() || !Point.SpawnTransform.GetRotation().IsNormalized()
            || Scale.X <= 0.0 || Scale.Y <= 0.0 || Scale.Z <= 0.0)
            return Reject(FString::Printf(TEXT("Spawn point %s has an invalid world capsule transform."), *Point.SpawnPointId.ToString()));
        PointsById.Add(Point.SpawnPointId, Point);
    }

    TArray<FRuntimeWave> NewWaves;
    TSet<FName> WaveIds;
    int32 TotalCount = 0;
    for (UNLWaveDefinition* Definition : Waves)
    {
        if (!IsValid(Definition)) return Reject(TEXT("A wave definition is missing."));
        if (Definition->WaveId.IsNone() || WaveIds.Contains(Definition->WaveId))
            return Reject(TEXT("Wave definitions require unique, nonempty WaveId values."));
        WaveIds.Add(Definition->WaveId);
        if (Definition->SpawnEntries.IsEmpty())
            return Reject(FString::Printf(TEXT("Wave %s has no spawn entries."), *Definition->WaveId.ToString()));
        if (!IsValidDuration(Definition->SpawnIntervalSeconds) || !IsValidDuration(Definition->IntermissionSeconds)
            || !IsValidDuration(Definition->RetryDelaySeconds))
            return Reject(TEXT("Wave timing values must be finite and nonnegative."));
        if (Definition->MaxAlive < 1 || Definition->MaxAlive > MaximumAliveEnemies)
            return Reject(TEXT("MaxAlive must be between 1 and 12; it is independent of attack slots."));
        if (Definition->MaxSpawnRetries < 0 || Definition->MaxSpawnRetries > MaximumSpawnRetries)
            return Reject(TEXT("MaxSpawnRetries must be between 0 and 32."));

        FRuntimeWave Wave;
        Wave.WaveId = Definition->WaveId;
        Wave.SpawnIntervalSeconds = Definition->SpawnIntervalSeconds;
        Wave.IntermissionSeconds = Definition->IntermissionSeconds;
        Wave.RetryDelaySeconds = Definition->RetryDelaySeconds;
        Wave.MaxAlive = Definition->MaxAlive;
        Wave.MaxSpawnRetries = Definition->MaxSpawnRetries;
        TArray<FNLWaveSpawnEntry> Entries = Definition->SpawnEntries;
        Entries.Sort([](const FNLWaveSpawnEntry& Left, const FNLWaveSpawnEntry& Right)
        {
            return NameBefore(Left.EntryId, Right.EntryId);
        });
        TSet<FName> EntryIds;
        for (const FNLWaveSpawnEntry& Entry : Entries)
        {
            UClass* EnemyClass = Entry.EnemyClass.Get();
            if (Entry.EntryId.IsNone() || EntryIds.Contains(Entry.EntryId))
                return Reject(TEXT("Each wave requires unique, nonempty EntryId values."));
            EntryIds.Add(Entry.EntryId);
            if (!EnemyClass || !EnemyClass->IsChildOf(ANLEnemyCharacter::StaticClass())
                || EnemyClass->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated | CLASS_NewerVersionExists))
                return Reject(FString::Printf(TEXT("Entry %s has no spawnable enemy class."), *Entry.EntryId.ToString()));
            if (Entry.Count < 1 || Entry.Count > MaximumPlannedEnemies - TotalCount
                || Entry.Count > MaximumPlannedEnemiesPerWave - Wave.Plan.Num())
                return Reject(TEXT("Entry counts must be positive; an encounter is capped at 1024 planned enemies and each wave at 512."));
            if (Entry.SpawnPointIds.IsEmpty())
                return Reject(FString::Printf(TEXT("Entry %s has no candidate spawn points."), *Entry.EntryId.ToString()));

            TArray<FName> CandidateIds = Entry.SpawnPointIds;
            CandidateIds.Sort([](FName Left, FName Right) { return NameBefore(Left, Right); });
            TArray<FNLWaveSpawnPoint> Candidates;
            TSet<FName> SeenPointIds;
            for (FName PointId : CandidateIds)
            {
                const FNLWaveSpawnPoint* Point = PointsById.Find(PointId);
                if (!Point || SeenPointIds.Contains(PointId))
                    return Reject(FString::Printf(TEXT("Entry %s has a missing or duplicate spawn point %s."), *Entry.EntryId.ToString(), *PointId.ToString()));
                SeenPointIds.Add(PointId);
                Candidates.Add(*Point);
            }
            RuntimeEnemyClasses.AddUnique(Entry.EnemyClass);
            for (int32 InstanceIndex = 0; InstanceIndex < Entry.Count; ++InstanceIndex)
            {
                FPlannedSpawn Planned;
                Planned.EnemyClass = Entry.EnemyClass;
                Planned.EntryId = Entry.EntryId;
                Planned.CandidatePoints = Candidates;
                Planned.InitialPointIndex = CompositionRandom.RandRange(0, Candidates.Num() - 1);
                Wave.Plan.Add(MoveTemp(Planned));
            }
            TotalCount += Entry.Count;
        }
        // This stream is used only for composition. Retries cycle authored points
        // without consuming randomness, so collision outcomes cannot reorder later waves.
        for (int32 Index = Wave.Plan.Num() - 1; Index > 0; --Index)
        {
            Wave.Plan.Swap(Index, CompositionRandom.RandRange(0, Index));
        }
        NewWaves.Add(MoveTemp(Wave));
    }

    int32 Ordinal = 0;
    for (FRuntimeWave& Wave : NewWaves)
    {
        for (FPlannedSpawn& Planned : Wave.Plan) Planned.SpawnOrdinal = Ordinal++;
    }
    RuntimeWaves = MoveTemp(NewWaves);
    PlannedCount = TotalCount;
    RuntimeMaxSpawnsPerTick = MaxSpawnsPerTick;
    RuntimeCorpseHoldSeconds = CorpseHoldSeconds;
    OutFailure = NAME_None;
    return true;
}

void ANLEncounterController::StartEncounter()
{
    if (bEndingPlay || bCleaningUp || (State != ENLEncounterState::Ready && State != ENLEncounterState::Cancelled)) return;
    const bool bWasPaused = bEncounterPaused;
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    ResetProgress(Seed);
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Ready);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Ready) return;
    FName Reason;
    if (!BuildPlan(Reason))
    {
        FailEncounter(Reason);
        return;
    }
    if (bWasPaused) SetEncounterPaused(true);
    BeginWave(0);
    // Start only changes state. The first spawn happens in a subsequent Tick.
}

void ANLEncounterController::CancelEncounter()
{
    if (bEndingPlay || bCleaningUp) return;
    const bool bCanBecomeCancelled = State == ENLEncounterState::Ready || State == ENLEncounterState::Cancelled || IsRunning();
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    bSpawnInProgress = false;
    NextSpawnAt = IntermissionEndsAt = 0.0;
    if (bCanBecomeCancelled) SetState(ENLEncounterState::Cancelled);
}

void ANLEncounterController::ResetEncounterForRetry(int32 InSeed, bool bStartImmediately)
{
    if (bEndingPlay || bCleaningUp) return;
    ++EncounterGeneration;
    CleanupOwnedEnemies();
    ResetProgress(InSeed);
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Ready);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Ready) return;
    FName Reason;
    if (!BuildPlan(Reason))
    {
        FailEncounter(Reason);
        return;
    }
    if (bStartImmediately) StartEncounter();
}

void ANLEncounterController::SetEncounterPaused(bool bPaused)
{
    if (bEndingPlay || bCleaningUp || bEncounterPaused == bPaused || !GetWorld()) return;
    const double Now = GetWorld()->GetTimeSeconds();
    if (bPaused)
    {
        PauseBeganWorldTime = Now;
    }
    else
    {
        AccumulatedPauseSeconds += FMath::Max(0.0, Now - PauseBeganWorldTime);
        PauseBeganWorldTime = 0.0;
    }
    bEncounterPaused = bPaused;
    const uint64 Generation = EncounterGeneration;
    // Copy weak handles because an external delegate may cancel/reset during a pause.
    TArray<TWeakObjectPtr<ANLEnemyCharacter>> Enemies;
    for (const FOwnedEnemy& Record : OwnedEnemies) Enemies.Add(Record.Enemy);
    for (const TWeakObjectPtr<ANLEnemyCharacter>& WeakEnemy : Enemies)
    {
        if (EncounterGeneration != Generation) return;
        if (ANLEnemyCharacter* Enemy = WeakEnemy.Get())
        {
            Enemy->SetLabPaused(bPaused || State == ENLEncounterState::Failed);
            // A controller-only pause must freeze animation/movement as well as its clock.
            Enemy->SetActorTickEnabled(!bPaused);
            Enemy->GetMesh()->SetComponentTickEnabled(!bPaused);
            Enemy->GetCharacterMovement()->SetComponentTickEnabled(!bPaused && State != ENLEncounterState::Failed);
            if (AAIController* AI = Cast<AAIController>(Enemy->GetController()))
                AI->SetActorTickEnabled(!bPaused && State != ENLEncounterState::Failed);
        }
    }
}

void ANLEncounterController::FailEncounter(FName Reason)
{
    if (bEndingPlay || bCleaningUp || State == ENLEncounterState::Failed || State == ENLEncounterState::Completed
        || State == ENLEncounterState::Cancelled) return;
    FailureReason = Reason.IsNone() ? FName(TEXT("InvalidWaveConfig")) : Reason;
    NextSpawnAt = IntermissionEndsAt = 0.0;
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Failed);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Failed) return;
    StopOwnedEnemies();
    if (EncounterGeneration != Generation || State != ENLEncounterState::Failed || bTerminalOutcomeEmitted) return;
    bTerminalOutcomeEmitted = true;
    UE_LOG(LogNLEncounter, Warning, TEXT("%s failed: %s (wave=%d spawned=%d defeated=%d)"),
        *GetName(), *FailureReason.ToString(), CurrentWaveIndex, SpawnedCount, DefeatedCount);
    OnEncounterFailed.Broadcast(FailureReason);
}

void ANLEncounterController::BeginWave(int32 WaveIndex)
{
    if (!RuntimeWaves.IsValidIndex(WaveIndex))
    {
        FailEncounter(TEXT("InvalidWaveConfig"));
        return;
    }
    CurrentWaveIndex = WaveIndex;
    NextSpawnAt = GetEncounterTime();
    SetState(ENLEncounterState::Spawning);
}

void ANLEncounterController::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bEndingPlay || bCleaningUp || bEncounterPaused || !GetWorld() || GetWorld()->IsPaused()) return;
    const uint64 Generation = EncounterGeneration;
    CleanupExpiredCorpses();
    if (EncounterGeneration != Generation || !IsRunning()) return;
    AuditOwnedEnemies();
    if (EncounterGeneration != Generation || !IsRunning()) return;

    if (State == ENLEncounterState::Intermission)
    {
        if (GetEncounterTime() >= IntermissionEndsAt) BeginWave(CurrentWaveIndex + 1);
        return;
    }
    if (State == ENLEncounterState::Spawning)
    {
        // Each attempt, including a failure with a zero retry delay, consumes budget.
        for (int32 Attempt = 0; Attempt < RuntimeMaxSpawnsPerTick; ++Attempt)
        {
            if (EncounterGeneration != Generation || State != ENLEncounterState::Spawning || bEncounterPaused) return;
            if (!RuntimeWaves.IsValidIndex(CurrentWaveIndex))
            {
                FailEncounter(TEXT("InvalidWaveConfig"));
                return;
            }
            const FRuntimeWave& Wave = RuntimeWaves[CurrentWaveIndex];
            if (Wave.NextPlanIndex >= Wave.Plan.Num() || GetAliveCount() >= Wave.MaxAlive
                || GetEncounterTime() < NextSpawnAt || bSpawnInProgress) break;
            if (!TrySpawnNext()) break;
        }
    }
    if (EncounterGeneration == Generation && IsRunning() && !bEncounterPaused) EvaluateWaveClear();
}

bool ANLEncounterController::TrySpawnNext()
{
    if (!RuntimeWaves.IsValidIndex(CurrentWaveIndex)) return false;
    FRuntimeWave& Wave = RuntimeWaves[CurrentWaveIndex];
    if (!Wave.Plan.IsValidIndex(Wave.NextPlanIndex)) return false;
    // Do not keep plan references across construction scripts or state delegates.
    const FPlannedSpawn Planned = Wave.Plan[Wave.NextPlanIndex];
    const int32 WaveIndex = CurrentWaveIndex;
    const int32 PlanIndex = Wave.NextPlanIndex;
    const uint64 Generation = EncounterGeneration;
    const int32 PointIndex = (Planned.InitialPointIndex + Planned.FailedAttempts) % Planned.CandidatePoints.Num();
    const FNLWaveSpawnPoint& Point = Planned.CandidatePoints[PointIndex];
    bSpawnInProgress = true;
    ANLEnemyCharacter* Enemy = GetWorld()->SpawnActorDeferred<ANLEnemyCharacter>(Planned.EnemyClass,
        Point.SpawnTransform, this, GetInstigator(), ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding);
    if (IsValid(Enemy)) Enemy->FinishSpawning(Point.SpawnTransform);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Spawning || bEndingPlay)
    {
        if (EncounterGeneration == Generation) bSpawnInProgress = false;
        if (IsValid(Enemy))
        {
            AAIController* AI = Cast<AAIController>(Enemy->GetController());
            Enemy->SetCombatEnabled(false);
            Enemy->GetEnemyBrain()->Despawn();
            Enemy->Destroy();
            if (IsValid(AI)) AI->Destroy();
        }
        return false;
    }
    bSpawnInProgress = false;
    if (!IsValid(Enemy))
    {
        FPlannedSpawn& Pending = RuntimeWaves[WaveIndex].Plan[PlanIndex];
        ++Pending.FailedAttempts;
        ++FailedSpawnCount;
        NextSpawnAt = GetEncounterTime() + RuntimeWaves[WaveIndex].RetryDelaySeconds;
        UE_LOG(LogNLEncounter, Warning, TEXT("%s: spawn ordinal %d at %s failed (attempt %d/%d)"),
            *GetName(), Planned.SpawnOrdinal, *Point.SpawnPointId.ToString(), Pending.FailedAttempts,
            RuntimeWaves[WaveIndex].MaxSpawnRetries + 1);
        if (Pending.FailedAttempts > RuntimeWaves[WaveIndex].MaxSpawnRetries) FailEncounter(TEXT("SpawnFailed"));
        return false;
    }

    UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain();
    UNLCombatIdentityComponent* Identity = Enemy->CombatIdentity;
    if (!Brain || !Identity || !Enemy->Vitals)
    {
        AAIController* AI = Cast<AAIController>(Enemy->GetController());
        Enemy->Destroy();
        if (IsValid(AI)) AI->Destroy();
        ++FailedSpawnCount;
        FailEncounter(TEXT("SpawnFailed"));
        return false;
    }

    FOwnedEnemy Record;
    Record.Enemy = Enemy;
    Record.SpawnedController = Cast<AAIController>(Enemy->GetController());
    Record.RuntimeId = Identity->EnsureRuntimeId();
    Record.Generation = Generation;
    Record.WaveIndex = WaveIndex;
    Record.SpawnOrdinal = Planned.SpawnOrdinal;
    OwnedEnemies.Add(Record);
    Brain->OnStateChanged.AddUniqueDynamic(this, &ANLEncounterController::HandleEnemyStateChanged);
    Enemy->OnDestroyed.AddUniqueDynamic(this, &ANLEncounterController::HandleOwnedEnemyDestroyed);
    ++RuntimeWaves[WaveIndex].NextPlanIndex;
    ++RuntimeWaves[WaveIndex].SpawnedCount;
    ++SpawnedCount;
    NextSpawnAt = GetEncounterTime() + RuntimeWaves[WaveIndex].SpawnIntervalSeconds;

    // ResetBrain preserves the authored spawn grace (0.35 seconds by default).
    // The identity and state listener exist before this can cause any transition.
    Brain->SpawnGraceSeconds = FMath::IsFinite(Brain->SpawnGraceSeconds)
        ? FMath::Max(0.35f, Brain->SpawnGraceSeconds) : 0.35f;
    Enemy->SetCombatEnabled(true);
    if (EncounterGeneration != Generation || !IsRunning()) return false;
    if (UNLAttackDirectorSubsystem* Director = GetWorld()->GetSubsystem<UNLAttackDirectorSubsystem>())
    {
        if (!Director->TryRegisterActiveFighter(Enemy))
        {
            UE_LOG(LogNLEncounter, Warning, TEXT("%s: spawned enemy could not join the active-fighter budget."), *GetName());
            ++FailedSpawnCount;
            FailEncounter(TEXT("SpawnFailed"));
            return false;
        }
    }
    else
    {
        ++FailedSpawnCount;
        FailEncounter(TEXT("SpawnFailed"));
        return false;
    }
    if (bEncounterPaused)
    {
        Enemy->SetLabPaused(true);
        Enemy->SetActorTickEnabled(false);
        Enemy->GetMesh()->SetComponentTickEnabled(false);
        Enemy->GetCharacterMovement()->SetComponentTickEnabled(false);
        if (AAIController* AI = Cast<AAIController>(Enemy->GetController())) AI->SetActorTickEnabled(false);
    }
    return true;
}

void ANLEncounterController::EvaluateWaveClear()
{
    if (!RuntimeWaves.IsValidIndex(CurrentWaveIndex) || bSpawnInProgress) return;
    const FRuntimeWave& Wave = RuntimeWaves[CurrentWaveIndex];
    if (Wave.NextPlanIndex < Wave.Plan.Num()) return;
    if (GetAliveCount() > 0)
    {
        SetState(ENLEncounterState::WaitingClear);
        return;
    }
    ++CompletedWaveCount;
    if (CurrentWaveIndex + 1 < RuntimeWaves.Num())
    {
        IntermissionEndsAt = GetEncounterTime() + Wave.IntermissionSeconds;
        SetState(ENLEncounterState::Intermission);
        return;
    }
    const uint64 Generation = EncounterGeneration;
    SetState(ENLEncounterState::Completed);
    if (EncounterGeneration != Generation || State != ENLEncounterState::Completed || bTerminalOutcomeEmitted) return;
    bTerminalOutcomeEmitted = true;
    OnEncounterCompleted.Broadcast();
}

ANLEncounterController::FOwnedEnemy* ANLEncounterController::FindOwnedEnemy(const ANLEnemyCharacter* Enemy)
{
    return OwnedEnemies.FindByPredicate([this, Enemy](const FOwnedEnemy& Record)
    {
        return Record.Generation == EncounterGeneration && Record.Enemy.Get() == Enemy;
    });
}

const ANLEncounterController::FOwnedEnemy* ANLEncounterController::FindOwnedEnemy(const ANLEnemyCharacter* Enemy) const
{
    return OwnedEnemies.FindByPredicate([this, Enemy](const FOwnedEnemy& Record)
    {
        return Record.Generation == EncounterGeneration && Record.Enemy.Get() == Enemy;
    });
}

void ANLEncounterController::HandleEnemyStateChanged(AActor* EnemyActor, ENLEnemyState PreviousState, ENLEnemyState NewState)
{
    if (bCleaningUp || bEndingPlay || !IsRunning()) return;
    ANLEnemyCharacter* Enemy = Cast<ANLEnemyCharacter>(EnemyActor);
    FOwnedEnemy* Record = FindOwnedEnemy(Enemy);
    if (!Record || Record->Terminal != EOwnedTerminal::Active) return;
    if (!Enemy->CombatIdentity || Enemy->CombatIdentity->GetRuntimeId() != Record->RuntimeId)
    {
        Record->Terminal = EOwnedTerminal::Destroyed;
        FailEncounter(TEXT("EnemyRemoved"));
        return;
    }
    if (NewState == ENLEnemyState::Dead)
    {
        // A stable ordinal/runtime identity can produce only one defeat event.
        Record->Terminal = EOwnedTerminal::Defeated;
        const float Length = Enemy->DeathAnimation ? Enemy->DeathAnimation->GetPlayLength() : 0.0f;
        Record->CorpseExpiresAt = GetEncounterTime() + (IsValidDuration(Length) ? Length : 0.0f) + RuntimeCorpseHoldSeconds;
        ++DefeatedCount;
        const FGuid RuntimeId = Record->RuntimeId;
        const int32 Ordinal = Record->SpawnOrdinal;
        OnEnemyDefeated.Broadcast(Enemy, RuntimeId, Ordinal);
        // Evaluation happens in Tick, after all synchronous death listeners finish.
    }
    else if (NewState == ENLEnemyState::Despawn)
    {
        Record->Terminal = EOwnedTerminal::Despawned;
        UE_LOG(LogNLEncounter, Warning, TEXT("%s: owned enemy ordinal %d despawned before defeat (health %.1f)."),
            *GetName(), Record->SpawnOrdinal, Enemy->Vitals ? Enemy->Vitals->GetHealth() : -1.0f);
        FailEncounter(TEXT("NavigationFailed"));
    }
}

void ANLEncounterController::HandleOwnedEnemyDestroyed(AActor* EnemyActor)
{
    if (bCleaningUp || bEndingPlay) return;
    FOwnedEnemy* Record = FindOwnedEnemy(Cast<ANLEnemyCharacter>(EnemyActor));
    if (!Record || Record->Terminal != EOwnedTerminal::Active) return;
    Record->Terminal = EOwnedTerminal::Destroyed;
    if (IsRunning()) FailEncounter(TEXT("EnemyRemoved"));
}

void ANLEncounterController::AuditOwnedEnemies()
{
    const uint64 Generation = EncounterGeneration;
    for (int32 Index = 0; Index < OwnedEnemies.Num(); ++Index)
    {
        FOwnedEnemy& Record = OwnedEnemies[Index];
        if (Record.Generation != Generation || Record.Terminal != EOwnedTerminal::Active) continue;
        ANLEnemyCharacter* Enemy = Record.Enemy.Get();
        if (!IsValid(Enemy) || !Enemy->CombatIdentity || Enemy->CombatIdentity->GetRuntimeId() != Record.RuntimeId
            || !Enemy->GetEnemyBrain())
        {
            Record.Terminal = EOwnedTerminal::Destroyed;
            FailEncounter(TEXT("EnemyRemoved"));
            return;
        }
        const ENLEnemyState EnemyState = Enemy->GetEnemyBrain()->GetState();
        if (EnemyState == ENLEnemyState::Dead || EnemyState == ENLEnemyState::Despawn)
        {
            HandleEnemyStateChanged(Enemy, EnemyState, EnemyState);
            if (EncounterGeneration != Generation || !IsRunning()) return;
        }
    }
}

void ANLEncounterController::UnbindEnemy(ANLEnemyCharacter* Enemy)
{
    if (!Enemy) return;
    if (UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain())
        Brain->OnStateChanged.RemoveDynamic(this, &ANLEncounterController::HandleEnemyStateChanged);
    Enemy->OnDestroyed.RemoveDynamic(this, &ANLEncounterController::HandleOwnedEnemyDestroyed);
}

void ANLEncounterController::CleanupExpiredCorpses()
{
    const uint64 Generation = EncounterGeneration;
    const double Now = GetEncounterTime();
    for (int32 Index = OwnedEnemies.Num() - 1; Index >= 0; --Index)
    {
        FOwnedEnemy& Record = OwnedEnemies[Index];
        if (Record.Generation != Generation || Record.Terminal != EOwnedTerminal::Defeated
            || (Record.Enemy.IsValid() && Now < Record.CorpseExpiresAt)) continue;
        ANLEnemyCharacter* Enemy = Record.Enemy.Get();
        AAIController* AI = Record.SpawnedController.Get();
        // Presentation may start on a later safe tick; even a zero hold must
        // allow the pending/playing death clip to finish before retirement.
        if (Enemy && Enemy->IsDeathPresentationInProgress()) continue;
        UnbindEnemy(Enemy);
        Record.Enemy.Reset();
        Record.SpawnedController.Reset();
        if (Enemy) Enemy->Destroy();
        if (IsValid(AI)) AI->Destroy();
        if (EncounterGeneration != Generation || bEndingPlay) return;
        // Totals live in the cumulative counters; retired actor handles need no scan.
        OwnedEnemies.RemoveAt(Index, 1, EAllowShrinking::No);
    }
}

void ANLEncounterController::CleanupOwnedEnemies()
{
    if (bCleaningUp) return;
    bCleaningUp = true;
    // Generation has already advanced; no record is eligible for a new reward.
    for (FOwnedEnemy& Record : OwnedEnemies)
    {
        ANLEnemyCharacter* Enemy = Record.Enemy.Get();
        AAIController* AI = Record.SpawnedController.Get();
        Record.Terminal = EOwnedTerminal::CleanedUp;
        if (Enemy)
        {
            UnbindEnemy(Enemy);
            Enemy->SetCombatEnabled(false);
            if (UNLEnemyBrainComponent* Brain = Enemy->GetEnemyBrain()) Brain->Despawn();
            Enemy->Destroy();
        }
        if (IsValid(AI)) AI->Destroy();
        Record.Enemy.Reset();
        Record.SpawnedController.Reset();
    }
    bCleaningUp = false;
}

void ANLEncounterController::StopOwnedEnemies()
{
    const uint64 Generation = EncounterGeneration;
    TArray<TWeakObjectPtr<ANLEnemyCharacter>> Enemies;
    for (const FOwnedEnemy& Record : OwnedEnemies) Enemies.Add(Record.Enemy);
    for (const TWeakObjectPtr<ANLEnemyCharacter>& WeakEnemy : Enemies)
    {
        if (EncounterGeneration != Generation) return;
        if (ANLEnemyCharacter* Enemy = WeakEnemy.Get())
        {
            Enemy->SetCombatEnabled(false);
            Enemy->SetLabPaused(true);
            Enemy->GetCharacterMovement()->SetComponentTickEnabled(false);
            if (AAIController* AI = Cast<AAIController>(Enemy->GetController())) AI->SetActorTickEnabled(false);
        }
    }
}

void ANLEncounterController::SetState(ENLEncounterState NewState)
{
    if (State == NewState) return;
    const ENLEncounterState PreviousState = State;
    State = NewState;
    if (!bEndingPlay) OnStateChanged.Broadcast(PreviousState, NewState);
}
