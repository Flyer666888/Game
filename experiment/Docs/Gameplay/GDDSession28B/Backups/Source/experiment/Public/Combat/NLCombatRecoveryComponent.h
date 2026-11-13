#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Combat/NLCombatTypes.h"
#include "NLCombatRecoveryComponent.generated.h"

class UNLCombatIdentityComponent;
class UNLCombatResolverSubsystem;
class UNLCombatVitalsComponent;

/** Validated perfect parries build a small automatic heal. Full health clears progress. */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLCombatRecoveryComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLCombatRecoveryComponent();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION(BlueprintPure, Category="Combat|Recovery")
	int32 GetRecoveryCharges() const { return RecoveryCharges; }

	UFUNCTION(BlueprintPure, Category="Combat|Recovery")
	int32 GetRequiredCharges() const { return FMath::Max(1, RequiredPerfectParries); }

	/** -1 until this life/retry has actually recovered health. Uses world game time. */
	UFUNCTION(BlueprintPure, Category="Combat|Recovery")
	double GetLastRecoveryTimeSeconds() const { return LastRecoveryTimeSeconds; }

	UFUNCTION(BlueprintPure, Category="Combat|Recovery")
	float GetLastRecoveredHealth() const { return LastRecoveredHealth; }

	/** Retry hook: clears charges, heal feedback, local pause and contact history. */
	UFUNCTION(BlueprintCallable, Category="Combat|Recovery")
	void ResetRecovery();

	UFUNCTION(BlueprintCallable, Category="Combat|Recovery")
	void SetCombatPaused(bool bPaused) { bCombatPaused = bPaused; }

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Recovery", meta=(ClampMin="1"))
	int32 RequiredPerfectParries = 3;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Recovery", meta=(ClampMin="0.0"))
	float HealAmount = 10.0f;

private:
	UFUNCTION()
	void HandleCombatResult(const FNLCombatResult& Result);

	UFUNCTION()
	void HandleVitalsChanged();

	UPROPERTY(Transient)
	TObjectPtr<UNLCombatResolverSubsystem> Resolver;

	UPROPERTY(Transient)
	TObjectPtr<UNLCombatVitalsComponent> Vitals;

	UPROPERTY(Transient)
	TObjectPtr<UNLCombatIdentityComponent> Identity;

	TSet<FGuid> SeenResultIds;
	TSet<FNLCombatHitKey> SeenParryContacts;
	int32 RecoveryCharges = 0;
	double LastRecoveryTimeSeconds = -1.0;
	float LastRecoveredHealth = 0.0f;
	bool bCombatPaused = false;
};
