#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Save/NLCheckpointTypes.h"
#include "NLRunStateSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FNLRunStateChanged);

/** Checkpoint-owned run state. Reward values/upgrades are configured by PROG-01 later. */
UCLASS()
class EXPERIMENT_API UNLRunStateSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category="Run")
    void BeginRun(FGuid InRunId);

    UFUNCTION(BlueprintPure, Category="Run")
    FGuid GetRunId() const { return RunId; }

    UFUNCTION(BlueprintPure, Category="Run")
    FNLProgressionState GetProgressionState() const { return Progression; }

    UFUNCTION(BlueprintCallable, Category="Run")
    bool RestoreProgressionState(const FNLProgressionState& State);

    /** Record a unique stable defeat event. This ledger does not grant currency. */
    UFUNCTION(BlueprintCallable, Category="Run")
    bool RecordEnemyDefeat(FName StableEventId);

    /** Returns true only on the first valid defeat; existing pending rewards remain recoverable. */
    UFUNCTION(BlueprintCallable, Category="Run|MasterRewards")
    bool RecordMasterDefeat(FName MasterId, FVector DropLocation);

    /** Durable claim. Only call after checking that a living player can receive health. */
    UFUNCTION(BlueprintCallable, Category="Run|MasterRewards")
    bool CollectMasterReward(FName MasterId);

    UFUNCTION(BlueprintPure, Category="Run|MasterRewards")
    bool HasDefeatedMaster(FName MasterId) const { return Progression.DefeatedMasterIds.Contains(MasterId); }

    UFUNCTION(BlueprintPure, Category="Run|MasterRewards")
    bool HasCollectedMasterReward(FName MasterId) const { return Progression.CollectedMasterRewards.Contains(MasterId); }

    /** Strict stable IDs keep unrelated elite enemies out of the four-master reward ledger. */
    static bool IsMasterId(FName MasterId);
    static bool ValidateMasterRewards(const FNLProgressionState& State);

    UFUNCTION(BlueprintPure, Category="Run")
    int32 GetDefeatEventCount() const { return Progression.RewardedEventIds.Num(); }

    UFUNCTION(BlueprintPure, Category="Run")
    FName GetLastFailureReason() const { return LastFailureReason; }

    UPROPERTY(BlueprintAssignable, Category="Run")
    FNLRunStateChanged OnRunStateChanged;

private:
    UPROPERTY(Transient)
    FGuid RunId;
    UPROPERTY(Transient)
    FNLProgressionState Progression;
    FName LastFailureReason = NAME_None;
    bool bMasterLedgerAvailable = true;

    bool LoadMasterLedger(FNLProgressionState& State);
    bool SaveMasterLedger(const FNLProgressionState& State);
};
