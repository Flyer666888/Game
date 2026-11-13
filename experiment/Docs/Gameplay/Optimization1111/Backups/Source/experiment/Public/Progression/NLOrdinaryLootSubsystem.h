#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "NLOrdinaryLootSubsystem.generated.h"

class ANLOrdinarySupplyPickup;
class UNLRunStateSubsystem;

UENUM(BlueprintType)
enum class ENLOrdinarySupplyKind : uint8
{
    None,
    Small,
    Large
};

/** Ordinary healing drops have a durable per-run ledger independent of checkpoint rollback. */
UCLASS()
class EXPERIMENT_API UNLOrdinaryLootSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

    /** The main-level director calls this once for an eligible ordinary defeat, never for master/Boss bodies. */
    UFUNCTION(BlueprintCallable, Category="Progression|OrdinarySupplies")
    bool RecordEligibleDefeat(FName StableEventId, FVector DropLocation);
    /** Prototype/test tuning is accepted only before the current run's first committed roll. */
    UFUNCTION(BlueprintCallable, Category="Progression|OrdinarySupplies")
    bool ConfigureDropRules(float DropProbability, int32 RandomSeed);
    UFUNCTION(BlueprintCallable, Category="Progression|OrdinarySupplies")
    void RestorePendingSupplies();
    UFUNCTION(BlueprintCallable, Category="Progression|OrdinarySupplies")
    bool TryCollect(FName StableEventId, AActor* Collector);
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    ANLOrdinarySupplyPickup* GetPendingSupply(FName StableEventId) const;
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    TArray<ANLOrdinarySupplyPickup*> GetPendingSupplies() const;
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    int32 GetProcessedCount() const { return Records.Num(); }
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    int32 GetConsecutiveMisses() const { return ConsecutiveMisses; }
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    ENLOrdinarySupplyKind GetSupplyKind(FName StableEventId) const;
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    bool HasProcessedEvent(FName StableEventId) const;
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    bool HasCollectedSupply(FName StableEventId) const;
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    FGuid GetRunId() const { return CurrentRunId; }
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    FName GetLastFailureReason() const { return LastFailureReason; }
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    float GetLastCollectedHealth() const { return LastCollectedHealth; }
    UFUNCTION(BlueprintPure, Category="Progression|OrdinarySupplies")
    double GetLastCollectedTimeSeconds() const { return LastCollectedTimeSeconds; }

    static float HealthForKind(ENLOrdinarySupplyKind Kind);
    static ENLOrdinarySupplyKind EvaluateRoll(float DropRoll, float SizeRoll, int32 Misses, float Probability);

private:
    friend class FNLOrdinaryLootPersistenceTest;
    struct FRecord
    {
        FName EventId;
        FVector Location = FVector::ZeroVector;
        ENLOrdinarySupplyKind Kind = ENLOrdinarySupplyKind::None;
        bool bCollected = false;
    };
    UFUNCTION()
    void HandleRunStateChanged();
    UNLRunStateSubsystem* ResolveRunState() const;
    void BindRunState();
    bool SynchronizeRun();
    bool LoadLedger();
    bool CommitLedger(const TArray<FRecord>& Candidate, int32 CandidateMisses, int32 CandidateSeed);
    ANLOrdinarySupplyPickup* CreatePendingSupply(const FRecord& Record);
    void ClearPendingActors();
    const FRecord* FindRecord(FName EventId) const;

    UPROPERTY(Transient)
    TObjectPtr<UNLRunStateSubsystem> BoundRunState;
    TArray<FRecord> Records;
    TMap<FName, TWeakObjectPtr<ANLOrdinarySupplyPickup>> PendingSupplies;
    FGuid CurrentRunId;
    int32 ConsecutiveMisses = 0;
    int32 RandomState = 0;
    float Probability = .2f;
    FName LastFailureReason;
    bool bLedgerAvailable = true;
    bool bRefreshing = false;
    bool bRefreshRequested = false;
    bool bSynchronizing = false;
    bool bClaiming = false;
    float LastCollectedHealth = 0;
    double LastCollectedTimeSeconds = -1000;
};
