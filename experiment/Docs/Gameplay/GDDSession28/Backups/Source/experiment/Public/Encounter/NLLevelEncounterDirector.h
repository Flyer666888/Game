#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Encounter/NLLevelEncounterTypes.h"
#include "Save/NLCheckpointTypes.h"
#include "NLLevelEncounterDirector.generated.h"

class ANLEncounterController;
class ANLEnemyCharacter;
class APawn;
class UNLCombatVitalsComponent;
class UNLRunStateSubsystem;
class UNLUpgradeDefinition;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FNLLevelStageChanged, FName, StageId, ENLLevelStageState, State);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FNLLevelMasterDefeated, FName, MasterId, FVector, Location);

/** Region gates around the finite, tested encounter controller; owns at most one encounter actor. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLLevelEncounterDirector : public AActor
{
    GENERATED_BODY()

public:
    ANLLevelEncounterDirector();
    virtual void Tick(float DeltaSeconds) override;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Level")
    TArray<FNLLevelEncounterStage> Stages;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Level")
    FName LevelId = TEXT("Level.Nilin.Playable");

    /** Optional first-ascent progression rules. Labs without a definition retain baseline damage. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Encounter|Progression")
    TObjectPtr<UNLUpgradeDefinition> UpgradeDefinition;

    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLLevelStageChanged OnStageChanged;

    /** Emitted only for a real owned-enemy defeat, once per MasterId during this level session. */
    UPROPERTY(BlueprintAssignable, Category="Encounter|Events")
    FNLLevelMasterDefeated OnMasterDefeated;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    ANLEncounterController* GetActiveEncounter() const;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    FName GetActiveStageId() const;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    FTransform GetRetryTransform() const;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    float GetRetryBurstEnergy() const { return EntryBurstEnergy; }

    UFUNCTION(BlueprintPure, Category="Encounter|Progression")
    FNLProgressionState GetRetryProgressionState() const { return EntryProgression; }

    /** Restore failed-stage growth before the player is revived. Durable master seals remain monotonic. */
    UFUNCTION(BlueprintCallable, Category="Encounter|Progression")
    bool RestoreRetryProgression();

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    ENLLevelStageState GetStageStatus(FName StageId) const;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    int32 GetCompletedStageCount() const;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    int32 GetStageCount() const { return RuntimeStages.Num(); }

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    float GetWarningRemaining() const;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    FName GetFailureReason() const { return FailureReason; }

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    bool IsBusy() const;

    UFUNCTION(BlueprintPure, Category="Encounter|Level")
    bool GetStageDefinition(FName StageId, FNLLevelEncounterStage& OutStage) const;

    UFUNCTION(BlueprintPure, Category="Encounter|Gate")
    TArray<FName> GetMissingSealIds(FName StageId) const;

    UFUNCTION(BlueprintPure, Category="Encounter|Gate")
    FName GetBlockedStageId() const;

    UFUNCTION(BlueprintPure, Category="Encounter|Gate")
    FName GetEntryBlockReason() const { return EntryBlockReason; }

    /** Optional explicit entry route; applies exactly the same bounds, dependency and living-player gates as Tick. */
    UFUNCTION(BlueprintCallable, Category="Encounter|Level")
    bool TryActivateStage(FName StageId, APawn* TriggeringPawn);

    /** Requires a living player after the caller has reset/respawned them. Cleared stages stay cleared. */
    UFUNCTION(BlueprintCallable, Category="Encounter|Level")
    bool RetryActiveStage();

    UFUNCTION(BlueprintCallable, Category="Encounter|Level")
    void FailActiveStage(FName Reason);

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    friend class FNLLevelEncounterMasterRewardOrderingTest;

    UFUNCTION()
    void HandleEncounterCompleted();
    UFUNCTION()
    void HandleEncounterFailed(FName Reason);
    UFUNCTION()
    void HandleEnemyDefeated(ANLEnemyCharacter* Enemy, FGuid EnemyRuntimeId, int32 SpawnOrdinal);
    UFUNCTION()
    void HandlePlayerDied();
    UFUNCTION()
    void HandleRunStateChanged();

    int32 FindStageIndex(FName StageId) const;
    bool ValidateConfiguration(FName& OutReason) const;
    bool IsStageInside(int32 Index, const FVector& Location) const;
    bool IsLivingPlayer(const APawn* Pawn) const;
    APawn* FindPlayerPawn() const;
    bool HasClearedDependency(int32 Index) const;
    UNLRunStateSubsystem* ResolveRunState() const;
    bool BeginWarning(int32 Index, APawn* Pawn);
    void StartActiveEncounter();
    void ReleaseEncounter();
    void ReleasePlayerBinding();
    void SetStageState(int32 Index, ENLLevelStageState State);
    static bool IsFinalWaveFinalOrdinal(int32 SpawnOrdinal, int32 PlannedCount, int32 WaveIndex, int32 WaveCount);

    /** Snapshot protects an active run against accidental editor/Blueprint configuration edits. */
    UPROPERTY(Transient)
    TArray<FNLLevelEncounterStage> RuntimeStages;
    UPROPERTY(Transient)
    TObjectPtr<ANLEncounterController> ActiveEncounter;
    UPROPERTY(Transient)
    TObjectPtr<UNLRunStateSubsystem> BoundRunState;
    UPROPERTY(Transient)
    TObjectPtr<UNLUpgradeDefinition> RuntimeUpgradeDefinition;
    UPROPERTY(Transient)
    FNLProgressionState EntryProgression;
    TWeakObjectPtr<APawn> ActivePlayer;
    TWeakObjectPtr<UNLCombatVitalsComponent> ActiveVitals;
    TArray<ENLLevelStageState> StageStates;
    TSet<FName> RewardedMasters;
    FName FailureReason = NAME_None;
    FName BlockedStageId = NAME_None;
    FName EntryBlockReason = NAME_None;
    FGuid ObservedRunId;
    double EntryBlockedAt = -1.0;
    float EntryBurstEnergy = 0.0f;
    int32 ActiveStageIndex = INDEX_NONE;
    double WarningEndsAt = 0.0;
    bool bConfigurationValid = false;
    bool bEndingPlay = false;
    bool bChangingEncounter = false;
    bool bHasEntryProgression = false;
};
