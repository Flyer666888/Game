#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NLOrdinarySupplyPickup.generated.h"

class USphereComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

/** A small or large ordinary healing spirit; the loot subsystem owns the durable claim. */
UCLASS()
class EXPERIMENT_API ANLOrdinarySupplyPickup : public AActor
{
    GENERATED_BODY()
public:
    ANLOrdinarySupplyPickup();
    virtual void BeginPlay() override;
    bool InitializeSupply(FName InEventId, FGuid InRunId, float InHealthAmount);
    UFUNCTION(BlueprintCallable, Category="Pickup")
    bool TryCollect(AActor* Collector);
    UFUNCTION(BlueprintPure, Category="Pickup")
    FName GetEventId() const { return EventId; }
    UFUNCTION(BlueprintPure, Category="Pickup")
    FGuid GetRunId() const { return RewardRunId; }
    UFUNCTION(BlueprintPure, Category="Pickup")
    float GetHealthAmount() const { return HealthAmount; }
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Pickup")
    TObjectPtr<USphereComponent> CollectionSphere;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Pickup")
    TObjectPtr<UStaticMeshComponent> Visual;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Pickup")
    TObjectPtr<UTextRenderComponent> Label;
private:
    UFUNCTION()
    void HandleOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
        UPrimitiveComponent* OtherComponent, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);
    FName EventId;
    FGuid RewardRunId;
    float HealthAmount = 0;
    bool bInitialized = false;
};
