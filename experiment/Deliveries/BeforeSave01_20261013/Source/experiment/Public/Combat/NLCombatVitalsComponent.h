#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NLCombatVitalsComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FNLVitalsEvent);

/** Mutable combat state. Damage is applied by the combat resolver after its contact gates. */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLCombatVitalsComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLCombatVitalsComponent();
	virtual void BeginPlay() override;

	UFUNCTION(BlueprintPure, Category="Combat|Vitals")
	float GetHealth() const { return Health; }

	UFUNCTION(BlueprintPure, Category="Combat|Vitals")
	float GetMaxHealth() const { return MaxHealth; }

	UFUNCTION(BlueprintPure, Category="Combat|Vitals")
	float GetGuard() const { return Guard; }

	UFUNCTION(BlueprintPure, Category="Combat|Vitals")
	float GetMaxGuard() const { return MaxGuard; }

	UFUNCTION(BlueprintPure, Category="Combat|Vitals")
	bool IsDead() const { return Health <= 0.0f; }

	UFUNCTION(BlueprintPure, Category="Combat|Vitals")
	bool IsDamageProtected() const;

	/** Returns the actual health removed. Only the combat resolver calls this damage entry point. */
	float ApplyCombatDamage(float RequestedDamage);

	/** Guard rules spend and restore resource through these clamped mutations. */
	float ConsumeGuard(float RequestedAmount);
	float RestoreGuard(float RequestedAmount);

	UFUNCTION(BlueprintCallable, Category="Combat|Vitals")
	void ResetVitals();

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Vitals", meta=(ClampMin="0.0"))
	float MaxHealth = 100.0f;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Vitals")
	float Health = 100.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Vitals", meta=(ClampMin="0.0"))
	float MaxGuard = 100.0f;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Vitals")
	float Guard = 100.0f;

	/** Uses game time, so a pause cannot consume the protection window. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Vitals", meta=(ClampMin="0.0"))
	float DamageProtectionSeconds = 0.65f;

	UPROPERTY(BlueprintAssignable, Category="Combat|Events")
	FNLVitalsEvent OnVitalsChanged;

	UPROPERTY(BlueprintAssignable, Category="Combat|Events")
	FNLVitalsEvent OnDied;

private:
	double LastDamageTime = 0.0;
	bool bHasTakenDamage = false;
};
