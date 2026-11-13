#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AI/NLEnemyTypes.h"
#include "Encounter/NLWaveTypes.h"
#include "NLEncounterController.generated.h"

class ANLEnemyCharacter;
class ASkeletalMeshActor;
class UNLWaveDefinition;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FNLEncounterStateChanged, ENLEncounterState, PreviousState, ENLEncounterState, NewState);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FNLEncounterEnemyDefeated, ANLEnemyCharacter*, Enemy, FGuid, EnemyRuntimeId, int32, SpawnOrdinal);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FNLEncounterCompleted);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FNLEncounterFailed, FName, Reason);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FNLWaveEntryReady, int32, WaveIndex);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FNLEncounterPauseChanged, bool, bPaused);

/** Explicitly started finite encounter. It owns only the enemies that it spawns. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLEncounterController : public AActor
{
    GENERATED_BODY()

public:
    ANLEncounterController();
    virtual void Tick(float DeltaSeconds) override;

    UFUNCTION(BlueprintCallable, Category="Encounter")
    void StartEncounter();
    UFUNCTION(BlueprintCallable, Category="Encounter")
    void CancelEncounter();
    UFUNCTION(BlueprintCallable, Category="Encounter")
    void ResetEncounterForRetry(int32 InSeed, bool bStartImmediately = false);
    /** Validate a section-entry snapshot without changing the encounter or its actors. */
    bool CanRestoreWaveEntry(int32 InInitialSeed, int32 EntryWaveIndex, int32 ExpectedRandomState,
        const TArray<FName>& ExpectedWaveIds, FName& OutReason) const;
    UFUNCTION(BlueprintCallable, Category="Encounter|Checkpoint")
    bool RestoreWaveEntry(int32 InInitialSeed, int32 EntryWaveIndex, int32 ExpectedRandomState,
        const TArray<FName>& ExpectedWaveIds);
    UFUNCTION(BlueprintCallable, Category="Encounter")
    void SetEncounterPaused(bool bPaused);
    UFUNCTION(BlueprintCallable, Category="Encounter")
    void FailEncounter(FName Reason);

    /** Stop the remaining spawn plan without cancelling the already living enemies or their attacks. */
    UFUNCTION(BlueprintCallable, Category="Encounter|Objective")
    void StopSpawningForObjective();
    UFUNCTION(BlueprintPure, Category="Encounter|Objective")
    bool IsSpawningStoppedForObjective() const { return bObjectiveSpawningStopped; }

    UFUNCTION(BlueprintPure, Category="Encounter")
    ENLEncounterState GetState() const { return State; }
    UFUNCTION(BlueprintPure, Category="Encounter")
    bool IsRunning() const;
    UFUNCTION(BlueprintPure, Category="Encounter")
    bool IsEncounterPaused() const { return bEncounterPaused; }
    UFUNCTION(BlueprintPure, Category="Encounter")
    bool OwnsEnemy(const ANLEnemyCharacter* Enemy) const;
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetInitialSeed() const { return InitialSeed; }
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetCurrentRandomSeed() const { return CompositionRandom.GetCurrentSeed(); }
    /** Authored wave order; entry and spawn-point IDs within each wave are sorted before planning. */
    UFUNCTION(BlueprintPure, Category="Encounter|Checkpoint")
    TArray<FName> GetWaveIds() const;
    /** All waves are preplanned: this is the final composition state at every section entry. */
    UFUNCTION(BlueprintPure, Category="Encounter|Checkpoint")
    int32 GetWaveEntryRandomState() const { return CompositionRandom.GetCurrentSeed(); }
    /** The next Ready/Cancelled start uses this zero-based section entry. */
    UFUNCTION(BlueprintPure, Category="Encounter|Checkpoint")
    int32 GetEntryWaveIndex() const { return ReadyStartingWaveIndex; }
    UFUNCTION(BlueprintPure, Category="Encounter|Checkpoint")
    bool IsRestoringWaveEntry() const { return bRestoringWaveEntry; }
    UFUNCTION(BlueprintPure, Category="Encounter|Checkpoint")
    FName GetCheckpointRestoreFailureReason() const { return CheckpointRestoreFailureReason; }
    /** Zero based; INDEX_NONE before a start. */
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetWaveIndex() const { return CurrentWaveIndex; }
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetWaveCount() const;
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetCompletedWaveCount() const { return CompletedWaveCount; }
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetPlannedCount() const { return PlannedCount; }
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetSpawnedCount() const { return SpawnedCount; }
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetDefeatedCount() const { return DefeatedCount; }
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetAliveCount() const;
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetFailedSpawnCount() const { return FailedSpawnCount; }
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetCurrentWavePlannedCount() const;
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    int32 GetCurrentWaveSpawnedCount() const;
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    float GetIntermissionRemaining() const;
    UFUNCTION(BlueprintPure, Category="Encounter|Progress")
    FName GetFailureReason() const { return FailureReason; }
    UFUNCTION(BlueprintPure, Category="Encounter|Presentation")
    int32 GetReadyPreviewCount() const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Configuration")
    TArray<TObjectPtr<UNLWaveDefinition>> Waves;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Configuration")
    TArray<FNLWaveSpawnPoint> SpawnPoints;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Configuration")
    int32 Seed = 20261012;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Checkpoint")
    FName LevelId = TEXT("Level.CombatLab.Waves");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Checkpoint")
    FName EncounterId = TEXT("Encounter.SwordWaves");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Checkpoint")
    FName ContentRevision = TEXT("SwordWaves.SAVE01.1");
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Checkpoint")
    bool bEnableCheckpoints = false;
    /** A level objective owns terminal success; finishing the last wave only stops further spawns. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Objective")
    bool bDeferCompletionToObjective = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Configuration", meta=(ClampMin="0.0"))
    float CorpseHoldSeconds = 2.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Configuration", meta=(ClampMin="1", ClampMax="12"))
    int32 MaxSpawnsPerTick = 1;
    /** Cosmetic, noncombat entry poses. VR enables these by default; other maps opt in. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Presentation")
    bool bShowReadyPreviews = false;

    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLEncounterStateChanged OnStateChanged;
    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLEncounterEnemyDefeated OnEnemyDefeated;
    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLEncounterCompleted OnEncounterCompleted;
    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLEncounterFailed OnEncounterFailed;
    /** Synchronous preparation/save boundary before Spawning or any enemy in this wave. */
    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLWaveEntryReady OnWaveEntryReady;
    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLEncounterPauseChanged OnPauseChanged;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    friend class FNLLevelObjectiveFlowTest;
    enum class EOwnedTerminal : uint8 { Active, Defeated, Despawned, Destroyed, CleanedUp };
    struct FPlannedSpawn
    {
        TSubclassOf<ANLEnemyCharacter> EnemyClass;
        FName EntryId;
        int32 SpawnOrdinal = INDEX_NONE;
        TArray<FNLWaveSpawnPoint> CandidatePoints;
        int32 NextPointIndex = 0;
        int32 FailedAttempts = 0;
    };
    struct FRuntimeWave
    {
        FName WaveId;
        TArray<FPlannedSpawn> Plan;
        float SpawnIntervalSeconds = 0.8f;
        float IntermissionSeconds = 3.0f;
        float RetryDelaySeconds = 0.5f;
        int32 MaxAlive = 3;
        int32 MaxSpawnRetries = 3;
        int32 NextPlanIndex = 0;
        int32 SpawnedCount = 0;
        FName LastSpawnPointId;
    };
    struct FOwnedEnemy
    {
        TWeakObjectPtr<ANLEnemyCharacter> Enemy;
        TWeakObjectPtr<class AAIController> SpawnedController;
        FGuid RuntimeId;
        uint64 Generation = 0;
        int32 WaveIndex = INDEX_NONE;
        int32 SpawnOrdinal = INDEX_NONE;
        EOwnedTerminal Terminal = EOwnedTerminal::Active;
        double CorpseExpiresAt = 0.0;
    };

    UFUNCTION()
    void HandleEnemyStateChanged(AActor* Enemy, ENLEnemyState PreviousState, ENLEnemyState NewState);
    UFUNCTION()
    void HandleOwnedEnemyDestroyed(AActor* Enemy);

    bool BuildPlan(FName& OutFailure);
    bool BuildPlanForSeed(int32 InSeed, TArray<FRuntimeWave>& OutWaves,
        TArray<TSubclassOf<ANLEnemyCharacter>>& OutEnemyClasses, FRandomStream& OutRandom,
        int32& OutPlannedCount, FName& OutFailure) const;
    bool BuildValidatedWaveEntry(int32 InInitialSeed, int32 EntryWaveIndex, int32 ExpectedRandomState,
        const TArray<FName>& ExpectedWaveIds, TArray<FRuntimeWave>& OutWaves,
        TArray<TSubclassOf<ANLEnemyCharacter>>& OutEnemyClasses, FRandomStream& OutRandom,
        int32& OutPlannedCount, FName& OutReason) const;
    void ApplyReadyWaveEntry(int32 EntryWaveIndex);
    bool TrySpawnNext();
    void BeginWave(int32 WaveIndex);
    void EvaluateWaveClear();
    void AuditOwnedEnemies();
    void CleanupExpiredCorpses();
    void CleanupOwnedEnemies();
    void UnbindEnemy(ANLEnemyCharacter* Enemy);
    void StopOwnedEnemies();
    void UpdateReadyPreviews();
    void CleanupReadyPreviews();
    void SetState(ENLEncounterState NewState);
    void ResetProgress(int32 InSeed);
    double GetEncounterTime() const;
    FOwnedEnemy* FindOwnedEnemy(const ANLEnemyCharacter* Enemy);
    const FOwnedEnemy* FindOwnedEnemy(const ANLEnemyCharacter* Enemy) const;

    TArray<FRuntimeWave> RuntimeWaves;
    TArray<FOwnedEnemy> OwnedEnemies;
    TArray<TWeakObjectPtr<ASkeletalMeshActor>> ReadyPreviews;
    UPROPERTY(Transient)
    TArray<TSubclassOf<ANLEnemyCharacter>> RuntimeEnemyClasses;
    FRandomStream CompositionRandom;
    ENLEncounterState State = ENLEncounterState::Ready;
    FName FailureReason = NAME_None;
    FName CheckpointRestoreFailureReason = NAME_None;
    uint64 EncounterGeneration = 0;
    int32 InitialSeed = 20261012;
    int32 CurrentWaveIndex = INDEX_NONE;
    int32 ReadyStartingWaveIndex = 0;
    int32 PlannedCount = 0;
    int32 SpawnedCount = 0;
    int32 DefeatedCount = 0;
    int32 FailedSpawnCount = 0;
    int32 CompletedWaveCount = 0;
    int32 RuntimeMaxSpawnsPerTick = 1;
    float RuntimeCorpseHoldSeconds = 2.0f;
    double NextSpawnAt = 0.0;
    double IntermissionEndsAt = 0.0;
    double PauseBeganWorldTime = 0.0;
    double AccumulatedPauseSeconds = 0.0;
    bool bEncounterPaused = false;
    bool bCleaningUp = false;
    bool bEndingPlay = false;
    bool bSpawnInProgress = false;
    bool bTerminalOutcomeEmitted = false;
    bool bRestoringWaveEntry = false;
    bool bWaveEntryInProgress = false;
    bool bReadyPreviewsBuilt = false;
    bool bObjectiveSpawningStopped = false;
    int32 ReadyPreviewWaveIndex = INDEX_NONE;
};
