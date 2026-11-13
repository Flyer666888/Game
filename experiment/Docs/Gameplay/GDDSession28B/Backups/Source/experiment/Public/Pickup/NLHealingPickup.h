#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NLHealingPickup.generated.h"

class USphereComponent;
class UStaticMeshComponent;
class UPointLightComponent;

/** One-shot master-first-defeat healing. Full-health/dead/non-player actors leave it intact. */
UCLASS()
class EXPERIMENT_API ANLHealingPickup : public AActor
{
    GENERATED_BODY()

public:
    ANLHealingPickup();
    virtual void BeginPlay() override;

    bool InitializeReward(FName InMasterId, FGuid InRunId, float InHealthAmount);

    UFUNCTION(BlueprintCallable, Category="Pickup")
    bool TryCollect(AActor* Collector);

    UFUNCTION(BlueprintPure, Category="Pickup")
    FName GetMasterId() const { return MasterId; }

    UFUNCTION(BlueprintPure, Category="Pickup")
    float GetHealthAmount() const { return HealthAmount; }

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Pickup")
    TObjectPtr<USphereComponent> CollectionSphere;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Pickup")
    TObjectPtr<UStaticMeshComponent> Visual;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Pickup")
    TObjectPtr<UPointLightComponent> Glow;

private:
    UFUNCTION()
    void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
        UPrimitiveComponent* OtherComponent, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

    FName MasterId;
    FGuid RewardRunId;
    float HealthAmount = 25.0f;
    bool bInitialized = false;
    bool bClaiming = false;
};
