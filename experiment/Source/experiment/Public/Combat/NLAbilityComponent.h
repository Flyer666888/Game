#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Combat/NLAbilityTypes.h"
#include "Combat/NLCombatTypes.h"
#include "NLAbilityComponent.generated.h"

class UNLCombatIdentityComponent;
class UNLCombatResolverSubsystem;
class UNLCombatVitalsComponent;
class UNLRunStateSubsystem;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FNLAbilityActivated, const FNLAreaControlResult&, Result);

/** Pulse and charged Burst share resolver-owned control, game time and checkpoint resource state. */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLAbilityComponent : public UActorComponent
{
	GENERATED_BODY()
public:
	UNLAbilityComponent();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UFUNCTION(BlueprintCallable, Category="Combat|Abilities") bool TryActivatePulse();
	UFUNCTION(BlueprintCallable, Category="Combat|Abilities") bool TryActivateBurst();
	UFUNCTION(BlueprintPure, Category="Combat|Abilities") float GetPulseCooldownRemaining() const;
	UFUNCTION(BlueprintPure, Category="Combat|Abilities") float GetBurstEnergy() const { return BurstEnergy; }
	UFUNCTION(BlueprintPure, Category="Combat|Abilities") float GetMaxBurstEnergy() const { return 100.0f; }
	UFUNCTION(BlueprintPure, Category="Combat|Abilities") FString GetAbilityStatusText() const;
	UFUNCTION(BlueprintPure, Category="Combat|Abilities") FNLAreaControlResult GetLastAbilityResult() const { return LastResult; }
	UFUNCTION(BlueprintPure, Category="Combat|Abilities") double GetLastActivationTimeSeconds() const { return LastActivationTime; }
	UFUNCTION(BlueprintPure, Category="Combat|Abilities") FName GetLastFailureReason() const { return LastFailureReason; }
	/** Retry restores entry energy, clears transient cooldown/contact/input state; it never grants energy. */
	UFUNCTION(BlueprintCallable, Category="Combat|Abilities") void RestoreAbilityState(float EntryBurstEnergy);
	UFUNCTION(BlueprintCallable, Category="Combat|Abilities") void SetCombatPaused(bool bPaused);

	// Pulse values are the GDD 10.5 starting point. The remaining values are explicit prototype tuning.
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Pulse", meta=(ClampMin="0.0")) float PulseCooldownSeconds = 8.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Pulse", meta=(ClampMin="1.0", ClampMax="2000.0")) float PulseRadiusCm = 250.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Pulse", meta=(ClampMin="0.0", ClampMax="5.0")) float PulseStaggerSeconds = 1.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Pulse", meta=(ClampMin="0.0", ClampMax="200.0")) float PulseKnockbackCm = 60.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Burst", meta=(ClampMin="1.0", ClampMax="2000.0")) float BurstRadiusCm = 400.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Burst", meta=(ClampMin="0.0", ClampMax="5.0")) float BurstStaggerSeconds = 2.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Burst", meta=(ClampMin="0.0", ClampMax="200.0")) float BurstKnockbackCm = 100.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Energy", meta=(ClampMin="0.0", ClampMax="100.0")) float EnergyPerDamagingHit = 3.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Energy", meta=(ClampMin="0.0", ClampMax="100.0")) float EnergyPerDefeat = 15.0f;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Abilities|Energy", meta=(ClampMin="0.0", ClampMax="100.0")) float EnergyPerPerfectParry = 12.0f;
	UPROPERTY(BlueprintAssignable, Category="Combat|Abilities") FNLAbilityActivated OnAbilityActivated;

private:
	bool TryActivate(ENLAreaAbility Ability);
	void SetEnergy(float Value);
	UFUNCTION() void HandleCombatResult(const FNLCombatResult& Result);
	UFUNCTION() void HandleRunStateChanged();
	UPROPERTY(Transient) TObjectPtr<UNLCombatIdentityComponent> Identity;
	UPROPERTY(Transient) TObjectPtr<UNLCombatVitalsComponent> Vitals;
	UPROPERTY(Transient) TObjectPtr<UNLCombatResolverSubsystem> Resolver;
	UPROPERTY(Transient) TObjectPtr<UNLRunStateSubsystem> RunState;
	TSet<FGuid> SeenResultIds;
	TSet<FNLCombatHitKey> SeenEnergyContacts;
	TSet<FGuid> RewardedDefeats;
	float BurstEnergy = 0.0f;
	double NextPulseTime = 0.0;
	double PauseBeganGameTime = 0.0;
	double LastActivationTime = -1000.0;
	FNLAreaControlResult LastResult;
	FName LastFailureReason = NAME_None;
	bool bCombatPaused = false;
	bool bActivating = false;
};
