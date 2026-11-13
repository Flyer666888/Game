#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "NLMasterRewardSubsystem.generated.h"

class ANLHealingPickup;
class UNLRunStateSubsystem;

/** Rebuilds one pending healing pickup per defeated master, backed by the run's durable ledger. */
UCLASS()
class EXPERIMENT_API UNLMasterRewardSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;
    virtual void OnWorldBeginPlay(UWorld& InWorld) override;
    virtual void Deinitialize() override;

    /** Repeated notifications return the existing pending pickup; a collected reward never respawns. */
    UFUNCTION(BlueprintCallable, Category="Progression|MasterRewards")
    ANLHealingPickup* SpawnFirstDefeatReward(FName MasterId, FVector Location, AActor* InstigatorOptional = nullptr);

    UFUNCTION(BlueprintCallable, Category="Progression|MasterRewards")
    void RestorePendingRewards();

    UFUNCTION(BlueprintPure, Category="Progression|MasterRewards")
    ANLHealingPickup* GetPendingReward(FName MasterId) const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Progression|MasterRewards", meta=(ClampMin="0.1", ClampMax="1000000.0"))
    float RewardHealthAmount = 25.0f;

private:
    UFUNCTION()
    void HandleRunStateChanged();

    UNLRunStateSubsystem* ResolveRunState() const;
    void BindRunState();
    ANLHealingPickup* CreatePendingReward(FName MasterId, FVector Location, AActor* Source);

    UPROPERTY(Transient)
    TObjectPtr<UNLRunStateSubsystem> BoundRunState;

    TMap<FName, TWeakObjectPtr<ANLHealingPickup>> PendingRewards;
    FGuid CurrentRunId;
    bool bRefreshing = false;
};
