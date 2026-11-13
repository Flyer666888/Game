#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AI/NLEnemyTypes.h"
#include "NLTalismanAttackComponent.generated.h"

class UNLEnemyBrainComponent;
class UNLAttackDefinition;
class UStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

/** A warning owns one immutable aim snapshot and at most one shared combat projectile. */
UCLASS(ClassGroup=(Combat), BlueprintType, Blueprintable, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLTalismanAttackComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UNLTalismanAttackComponent();

    UFUNCTION(BlueprintCallable, Category="Combat|Enemy|Talisman")
    void ResetForEncounter();

    /** The director and the projectile share this hand position, with a chest fallback. */
    UFUNCTION(BlueprintPure, Category="Combat|Enemy|Talisman")
    FVector GetMuzzlePosition() const;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman")
    FName MuzzleSocketName = TEXT("hand_l");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman")
    FVector MuzzleLocalOffset = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman")
    FVector FallbackMuzzleOffset = FVector(0,0,40);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman", meta=(ClampMin="0.1", Units="cm"))
    float ProjectileRadius = 7.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman", meta=(ClampMin="0.1", Units="s"))
    float ProjectileLifetimeSeconds = 4.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance")
    FTransform TalismanHandTransform;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance")
    TObjectPtr<UMaterialInterface> TalismanMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance")
    TObjectPtr<UMaterialInterface> CastGlowMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance")
    TObjectPtr<UMaterialInterface> ProjectileMaterial;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Enemy|Talisman|Appearance")
    TObjectPtr<UStaticMeshComponent> TalismanVisual;

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Enemy|Talisman|Appearance")
    TObjectPtr<UStaticMeshComponent> CastGlow;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction) override;

private:
    UFUNCTION()
    void HandleStateChanged(AActor* Enemy, ENLEnemyState PreviousState, ENLEnemyState NewState);
    UFUNCTION()
    void HandleAttackStarted(AActor* Enemy, AActor* Target);
    UFUNCTION()
    void HandleAttackEnded(AActor* Enemy, AActor* Target);
    UFUNCTION()
    void HandleAttackCancelled(AActor* Enemy, AActor* Target, FName Reason);

    bool IsCaster() const;
    bool IsPresentationAllowed() const;
    bool IsFireAllowed() const;
    UNLAttackDefinition* GetAttackDefinition() const;
    void EnsureVisuals();
    void RefreshVisualAttachment();
    void UpdatePresentation();
    void InvalidateWarning();

    TWeakObjectPtr<UNLEnemyBrainComponent> Brain;
    TWeakObjectPtr<AActor> WarnedTarget;
    FGuid WarnedAttackInstanceId;
    FVector WarnedAimPosition = FVector::ZeroVector;
    uint64 WarningEpoch = 0;
    uint64 ArmedEpoch = 0;
    float WarningElapsedSeconds = 0;
    bool bWarningArmed = false;
    bool bShotConsumed = false;

    UPROPERTY(Transient)
    TObjectPtr<UNLAttackDefinition> WarnedAttackDefinition;

    UPROPERTY(Transient)
    TObjectPtr<UMaterialInstanceDynamic> GlowMaterialInstance;
};
