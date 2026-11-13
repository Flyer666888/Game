#pragma once

#include "CoreMinimal.h"
#include "AI/NLEnemyCharacter.h"
#include "Combat/NLCombatTypes.h"
#include "NLGuardCaptainCharacter.generated.h"

class UBoxComponent;
class UNLGuardComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;

/** A front-facing formation ward, deliberate heavy swing and readable break opening. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLGuardCaptainCharacter : public ANLEnemyCharacter
{
    GENERATED_BODY()

public:
    ANLGuardCaptainCharacter();
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetCombatEnabled(bool bEnabled) override;
    virtual void SetLabPaused(bool bPaused) override;
    virtual void ResetForEncounter() override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Captain")
    TObjectPtr<UNLGuardComponent> CaptainGuard;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Captain")
    TObjectPtr<UBoxComponent> CaptainGuardCollision;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Captain")
    TObjectPtr<UStaticMeshComponent> CaptainGuardVisual;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Captain")
    TObjectPtr<UMaterialInterface> GuardFieldMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Captain", meta=(ClampMin="0.2", ClampMax="5.0"))
    float GuardBreakExposureSeconds = 1.2f;

    UFUNCTION(BlueprintPure, Category="Combat|Captain")
    float GetCounterWindowRemaining() const { return CounterWindowRemaining; }

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UFUNCTION()
    void HandleCaptainStateChanged(AActor* Enemy, ENLEnemyState PreviousState, ENLEnemyState NewState);
    UFUNCTION()
    void HandleCaptainGuardBroken();
    UFUNCTION()
    void HandleCaptainCombatResult(const FNLCombatResult& Result);
    void UpdateCaptainDefense();
    void UpdateCaptainStatus();

    UPROPERTY(Transient)
    TObjectPtr<UMaterialInstanceDynamic> GuardFieldInstance;
    float CounterWindowRemaining = 0.0f;
    float BlockFlashRemaining = 0.0f;
};
