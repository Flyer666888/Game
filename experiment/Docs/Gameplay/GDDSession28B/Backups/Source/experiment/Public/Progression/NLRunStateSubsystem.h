#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Save/NLCheckpointTypes.h"
#include "NLRunStateSubsystem.generated.h"

class UNLUpgradeDefinition;

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FNLRunStateChanged);

/** Checkpoint-owned growth with a separate durable four-master quest/reward ledger. */
UCLASS()
class EXPERIMENT_API UNLRunStateSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category="Run")
    void BeginRun(FGuid InRunId);

    /** Resume the level's last run, or atomically create its first run. Damaged records are preserved and rejected. */
    UFUNCTION(BlueprintCallable, Category="Run|Level")
    bool ResumeOrBeginLevelRun(FName LevelId);

    /** Explicit new-game operation. Existing per-run ledgers remain on disk for recovery. */
    UFUNCTION(BlueprintCallable, Category="Run|Level")
    bool BeginNewLevelRun(FName LevelId);

    UFUNCTION(BlueprintPure, Category="Run")
    FGuid GetRunId() const { return RunId; }

    UFUNCTION(BlueprintPure, Category="Run")
    FNLProgressionState GetProgressionState() const { return Progression; }

    UFUNCTION(BlueprintCallable, Category="Run")
    bool RestoreProgressionState(const FNLProgressionState& State);

    /** Record a unique stable defeat event. This ledger does not grant currency. */
    UFUNCTION(BlueprintCallable, Category="Run")
    bool RecordEnemyDefeat(FName StableEventId);

    /** Copies valid tuning for this level; nullptr disables effects without changing the saved growth. */
    UFUNCTION(BlueprintCallable, Category="Run|Growth")
    bool ConfigureUpgradeDefinition(UNLUpgradeDefinition* Definition);

    UFUNCTION(BlueprintPure, Category="Run|Growth")
    UNLUpgradeDefinition* GetUpgradeDefinition() const { return UpgradeDefinition; }

    /** Atomically grants one unique defeat reward. Repeated IDs return false without an error. */
    UFUNCTION(BlueprintCallable, Category="Run|Growth")
    bool AwardLingQi(FName StableEventId, float Amount);

    /** First-level safety floor. Repeated valid requests succeed without awarding currency or replaying feedback. */
    UFUNCTION(BlueprintCallable, Category="Run|Growth")
    bool EnsureUpgradeLevel(int32 MinimumLevel);

    UFUNCTION(BlueprintPure, Category="Run|Growth")
    float GetPlayerDamageMultiplier() const;

    UFUNCTION(BlueprintPure, Category="Run|Growth")
    float GetNextUpgradeThreshold() const;

    UFUNCTION(BlueprintPure, Category="Run|Growth")
    float GetLingQiPerDefeat() const { return UpgradeDefinition ? ConfiguredLingQiPerDefeat : 0.0f; }

    UFUNCTION(BlueprintPure, Category="Run|Growth")
    float GetLastLingQiAwardAmount() const { return LastLingQiAwardAmount; }

    UFUNCTION(BlueprintPure, Category="Run|Growth")
    double GetLastLingQiAwardTimeSeconds() const { return LastLingQiAwardTimeSeconds; }

    UFUNCTION(BlueprintPure, Category="Run|Growth")
    double GetLastUpgradeTimeSeconds() const { return LastUpgradeTimeSeconds; }

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

    /** Quest drops are automatically collected on a durable first defeat, independently of healing supplies. */
    UFUNCTION(BlueprintCallable, Category="Run|Seals")
    bool GrantMasterSeal(FName MasterId, FName SealId, FVector DropLocation);

    UFUNCTION(BlueprintPure, Category="Run|Seals")
    bool HasSeal(FName SealId) const;

    UFUNCTION(BlueprintPure, Category="Run|Seals")
    TArray<FName> GetCollectedSealIds() const;

    UFUNCTION(BlueprintPure, Category="Run|Seals")
    FName GetLastAcquiredSealId() const { return LastAcquiredSealId; }

    UFUNCTION(BlueprintPure, Category="Run|Seals")
    double GetLastSealAcquiredTimeSeconds() const { return LastSealAcquiredTimeSeconds; }

    UFUNCTION(BlueprintPure, Category="Run|Seals")
    static FText GetSealDisplayName(FName SealId);

    static FName SealForMaster(FName MasterId);
    static FName MasterForSeal(FName SealId);

    /** Strict stable IDs keep unrelated elite enemies out of the four-master reward ledger. */
    static bool IsMasterId(FName MasterId);
    static bool ValidateMasterRewards(const FNLProgressionState& State);

    UFUNCTION(BlueprintPure, Category="Run")
    int32 GetDefeatEventCount() const { return Progression.RewardedEventIds.Num(); }

    UFUNCTION(BlueprintPure, Category="Run")
    FName GetLastFailureReason() const { return LastFailureReason; }

    UFUNCTION(BlueprintPure, Category="Run|Seals")
    bool IsQuestProgressAvailable() const { return RunId.IsValid() && bMasterLedgerAvailable && bLevelRunAvailable; }

    /** Runtime resource synchronization; checkpoint serialization already carries this value. */
    UFUNCTION(BlueprintCallable, Category="Run")
    bool SetBurstEnergy(float Value);

    UPROPERTY(BlueprintAssignable, Category="Run")
    FNLRunStateChanged OnRunStateChanged;

private:
    UPROPERTY(Transient)
    FGuid RunId;
    UPROPERTY(Transient)
    FNLProgressionState Progression;
    UPROPERTY(Transient)
    TObjectPtr<UNLUpgradeDefinition> UpgradeDefinition;
    float ConfiguredLingQiPerDefeat = 0.0f;
    float ConfiguredFirstUpgradeThreshold = 0.0f;
    float ConfiguredLevelTwoDamageMultiplier = 1.0f;
    float LastLingQiAwardAmount = 0.0f;
    double LastLingQiAwardTimeSeconds = -1.0;
    double LastUpgradeTimeSeconds = -1.0;
    FName LastFailureReason = NAME_None;
    bool bMasterLedgerAvailable = true;
    bool bLevelRunAvailable = true;
    FName LastAcquiredSealId = NAME_None;
    double LastSealAcquiredTimeSeconds = -1.0;

    bool LoadMasterLedger(FNLProgressionState& State);
    bool SaveMasterLedger(const FNLProgressionState& State);
    void ResetGrowthFeedback();
};
