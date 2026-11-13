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
};
