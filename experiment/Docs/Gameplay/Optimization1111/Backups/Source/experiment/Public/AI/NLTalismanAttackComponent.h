#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AI/NLEnemyTypes.h"
#include "NLTalismanAttackComponent.generated.h"

class UNLEnemyBrainComponent;
class UNLAttackDefinition;
class UStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class ANLRitualObjective;

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

    UFUNCTION(BlueprintPure, Category="Combat|Enemy|Ritual")
    bool IsInterfering() const { return ChannelObjective.IsValid(); }

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

    /** Authored centimetre-sized prop. Null keeps the legacy ritual paper. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance")
    TObjectPtr<UStaticMesh> TalismanMesh;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance")
    bool bFloatBeforeHand = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance", meta=(ClampMin="10.0", Units="cm"))
    float FloatingHandDistanceCm = 17.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Talisman|Appearance", meta=(ClampMin="8.0", Units="cm"))
    float FloatingOrbDistanceCm = 13.0f;

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

    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Enemy|Ritual")
    TObjectPtr<UStaticMeshComponent> InterferenceLink;

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
    UFUNCTION()
    void HandleObjectiveChanged(ANLRitualObjective* Objective);

    bool IsCaster() const;
    bool IsPresentationAllowed() const;
    bool IsFireAllowed() const;
    UNLAttackDefinition* GetAttackDefinition() const;
    void EnsureVisuals();
    void RefreshVisualAttachment();
    void UpdatePresentation();
    void InvalidateWarning();
    void ClearInterference();
    FVector GetFloatingHandAnchorPosition() const;
    FVector GetFloatingTalismanPosition() const;

    TWeakObjectPtr<UNLEnemyBrainComponent> Brain;
    TWeakObjectPtr<AActor> WarnedTarget;
    FGuid WarnedAttackInstanceId;
    FVector WarnedAimPosition = FVector::ZeroVector;
    uint64 WarningEpoch = 0;
    uint64 ArmedEpoch = 0;
    float WarningElapsedSeconds = 0;
    float TalismanFloatAlpha = 0;
    bool bWarningArmed = false;
    bool bShotConsumed = false;
    TWeakObjectPtr<ANLRitualObjective> ChannelObjective;
    FName InterferenceSourceId = NAME_None;

    UPROPERTY(Transient)
    TObjectPtr<UNLAttackDefinition> WarnedAttackDefinition;

    UPROPERTY(Transient)
    TObjectPtr<UMaterialInstanceDynamic> GlowMaterialInstance;
};
